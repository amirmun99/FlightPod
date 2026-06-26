"""Shared pytest fixtures for the API test suite."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from flightpaper.api.app_state import AppState, build_app_state
from flightpaper.api.secure_envelope import (
    ENVELOPE_VERSION,
    RESPONSE_METHOD,
    build_aad,
    encrypt_envelope,
    seal_envelope,
)
from flightpaper.api.server import create_app
from flightpaper.security import crypto


# ---------------------------------------------------------------------------
# Mock OpenSky transport — returns the canned ``many`` scenario fixture.
# ---------------------------------------------------------------------------


def _mock_opensky_states(now_ts: int) -> dict[str, Any]:
    return {
        "time": now_ts,
        "states": [
            [
                "ac0001", "ACA123  ", "Canada",
                now_ts - 5, now_ts - 5,
                -79.81, 43.33,
                9525.0, False,
                240.0, 82.0, 0.0,
                None, 9540.0,
                "1234", False, 0,
            ]
        ],
    }


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/states/all"):
        import time as _t
        body = _mock_opensky_states(int(_t.time()))
        return httpx.Response(
            200,
            content=json.dumps(body),
            headers={"X-Rate-Limit-Remaining": "100", "Content-Type": "application/json"},
        )
    return httpx.Response(404, content="not found")


# ---------------------------------------------------------------------------
# AppState fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def app_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppState:
    # Pin the secure_dir at a tmp directory and skip mDNS / host detection.
    monkeypatch.setenv("FLIGHTPAPER_DEV", "1")
    state = build_app_state(
        secure_dir=tmp_path / "secure",
        opensky_transport=httpx.MockTransport(_mock_handler),
        host_provider_override="127.0.0.1",
    )
    yield state
    state.opensky_client.close()


@pytest.fixture
def client(app_state: AppState) -> TestClient:
    app = create_app(state=app_state, start_background_tasks=False)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers for pairing handshake from the "phone" side
# ---------------------------------------------------------------------------


@dataclass
class PairedSession:
    state: AppState
    client_id: str
    client_keypair: crypto.X25519KeyPair
    session_key: bytes


def perform_pairing(
    test_client: TestClient,
    *,
    state: AppState,
    client_id: str = "iphone_aabbccddeeff",
    app_instance_name: str | None = "Test iPhone",
) -> PairedSession:
    """Run a full pair handshake against the test client and return the session."""

    # The Pi has already auto-started a pairing window in build_app_state.
    pairing_status = test_client.get("/api/public/pairing-status").json()
    assert pairing_status["state"] == "pairing_pending"

    # Recover the QR payload (in a real flow the phone scans the QR; here
    # we read directly from PairingManager).
    qr_payload = state.pairing.qr_payload()
    pairing_secret = crypto.b64u_decode(qr_payload["pairing_secret"])
    device_pub = crypto.b64u_decode(qr_payload["device_pub"])
    device_id = qr_payload["device_id"]

    # Phone-side derivation of pairing_key (symmetric).
    pairing_key = crypto.derive_pairing_key(
        pairing_secret=pairing_secret,
        device_id=device_id,
        device_public_key=device_pub,
    )

    phone = crypto.generate_x25519_keypair()
    plaintext = json.dumps(
        {
            "client_pub": crypto.b64u_encode(phone.public_key),
            "app_instance_name": app_instance_name,
            "protocol_version": 1,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    ts = int(qr_payload["expires_at"] - 60)  # a sane recent timestamp
    nonce = crypto.random_nonce()
    aad = build_aad(
        v=ENVELOPE_VERSION,
        method="POST",
        path="/api/public/pair",
        device_id=device_id,
        client_id=client_id,
        key_id="pairing",
        seq=0,
        ts=ts,
    )
    ciphertext = crypto.aead_encrypt(
        key=pairing_key, nonce=nonce, plaintext=plaintext, aad=aad
    )

    envelope = {
        "v": ENVELOPE_VERSION,
        "device_id": device_id,
        "client_id": client_id,
        "key_id": "pairing",
        "seq": 0,
        "ts": ts,
        "nonce": crypto.b64u_encode(nonce),
        "ciphertext": crypto.b64u_encode(ciphertext),
    }
    response = test_client.post("/api/public/pair", json=envelope)
    assert response.status_code == 200, response.text
    response_env = response.json()

    # Phone decrypts the response envelope with the same pairing key.
    response_aad = build_aad(
        v=ENVELOPE_VERSION,
        method="RES",
        path="/api/public/pair",
        device_id=device_id,
        client_id=client_id,
        key_id="pairing",
        seq=int(response_env["seq"]),
        ts=int(response_env["ts"]),
    )
    response_pt = crypto.aead_decrypt(
        key=pairing_key,
        nonce=crypto.b64u_decode(response_env["nonce"]),
        ciphertext=crypto.b64u_decode(response_env["ciphertext"]),
        aad=response_aad,
    )
    response_body = json.loads(response_pt)
    assert response_body["ok"] is True
    assert response_body["device_id"] == device_id
    assert response_body["client_id"] == client_id

    # Phone derives the session key the same way the Pi did.
    shared = crypto.x25519_shared_secret(
        private_key=phone.private_key, peer_public_key=device_pub
    )
    session_key = crypto.derive_session_key(
        shared_secret=shared,
        pairing_secret=pairing_secret,
        device_id=device_id,
        client_id=client_id,
    )

    # Sanity: same key the Pi persisted.
    stored = state.key_store.get(client_id)
    assert stored is not None
    assert stored.session_key == session_key

    return PairedSession(
        state=state,
        client_id=client_id,
        client_keypair=phone,
        session_key=session_key,
    )


def send_secure(
    test_client: TestClient,
    *,
    session: PairedSession,
    method: str,
    path: str,
    body: dict[str, Any],
    seq: int,
    ts: int | None = None,
) -> httpx.Response:
    """Send a secure envelope and return the raw response."""

    import time as _t

    ts = ts if ts is not None else int(_t.time())
    envelope = seal_envelope(
        payload=body,
        key=session.session_key,
        method=method.upper(),
        path=path,
        device_id=session.state.identity.device_id,
        client_id=session.client_id,
        key_id="main",
        seq=seq,
        ts=ts,
    )
    if method.upper() == "GET":
        return test_client.request("GET", path, json=envelope)
    return test_client.request(method.upper(), path, json=envelope)


def open_response_envelope(
    *,
    session: PairedSession,
    envelope: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    """Decrypt an envelope returned by the server (key_id=main, method=RES)."""

    aad = build_aad(
        v=ENVELOPE_VERSION,
        method=RESPONSE_METHOD,
        path=path,
        device_id=session.state.identity.device_id,
        client_id=session.client_id,
        key_id="main",
        seq=int(envelope["seq"]),
        ts=int(envelope["ts"]),
    )
    plaintext = crypto.aead_decrypt(
        key=session.session_key,
        nonce=crypto.b64u_decode(envelope["nonce"]),
        ciphertext=crypto.b64u_decode(envelope["ciphertext"]),
        aad=aad,
    )
    return json.loads(plaintext)
