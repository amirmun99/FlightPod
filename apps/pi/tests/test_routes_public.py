"""Tests for /api/public/* — health, pairing-status, and the pair handshake."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from flightpaper.api.app_state import AppState
from flightpaper.api.secure_envelope import (
    ENVELOPE_VERSION,
    build_aad,
    encrypt_envelope,
)
from flightpaper.security import crypto

from .conftest import perform_pairing


# ---------------------------------------------------------------------------
# Health + pairing status
# ---------------------------------------------------------------------------


def test_health_endpoint(client: TestClient, app_state: AppState) -> None:
    resp = client.get("/api/public/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["device_id"] == app_state.identity.device_id
    assert "uptime_seconds" in body
    assert body["version"] == app_state.config.app.version


def test_pairing_status_starts_pending(client: TestClient, app_state: AppState) -> None:
    resp = client.get("/api/public/pairing-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "pairing_pending"
    assert body["device_id"] == app_state.identity.device_id
    assert body["pairing_expires_at"] is not None


def test_pairing_status_transitions_to_paired(client: TestClient, app_state: AppState) -> None:
    perform_pairing(client, state=app_state)
    body = client.get("/api/public/pairing-status").json()
    assert body["state"] == "paired"


# ---------------------------------------------------------------------------
# Pair handshake — happy path
# ---------------------------------------------------------------------------


def test_pair_round_trip(client: TestClient, app_state: AppState) -> None:
    session = perform_pairing(client, state=app_state, client_id="iphone_aabbccddeeff")
    # Pi stored the right paired client.
    stored = app_state.key_store.get(session.client_id)
    assert stored is not None
    assert stored.app_instance_name == "Test iPhone"


# ---------------------------------------------------------------------------
# Pair handshake — error paths
# ---------------------------------------------------------------------------


def _build_pair_envelope(
    *,
    app_state: AppState,
    pairing_key: bytes,
    plaintext: bytes,
    method: str = "POST",
    path: str = "/api/public/pair",
    client_id: str = "iphone_aabbccddeeff",
    seq: int = 0,
    ts: int = 1_700_000_000,
    device_id: str | None = None,
) -> dict:
    device_id = device_id or app_state.identity.device_id
    nonce = crypto.random_nonce()
    aad = build_aad(
        v=ENVELOPE_VERSION,
        method=method,
        path=path,
        device_id=device_id,
        client_id=client_id,
        key_id="pairing",
        seq=seq,
        ts=ts,
    )
    ciphertext = crypto.aead_encrypt(
        key=pairing_key, nonce=nonce, plaintext=plaintext, aad=aad
    )
    return {
        "v": ENVELOPE_VERSION,
        "device_id": device_id,
        "client_id": client_id,
        "key_id": "pairing",
        "seq": seq,
        "ts": ts,
        "nonce": crypto.b64u_encode(nonce),
        "ciphertext": crypto.b64u_encode(ciphertext),
    }


def _current_pairing_key(app_state: AppState) -> tuple[bytes, dict]:
    payload = app_state.pairing.qr_payload()
    key = crypto.derive_pairing_key(
        pairing_secret=crypto.b64u_decode(payload["pairing_secret"]),
        device_id=payload["device_id"],
        device_public_key=crypto.b64u_decode(payload["device_pub"]),
    )
    return key, payload


def test_pair_rejects_non_json(client: TestClient) -> None:
    resp = client.post("/api/public/pair", content="not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_request"


def test_pair_rejects_wrong_device_id(client: TestClient, app_state: AppState) -> None:
    key, _ = _current_pairing_key(app_state)
    phone = crypto.generate_x25519_keypair()
    pt = json.dumps({"client_pub": crypto.b64u_encode(phone.public_key)}).encode()
    env = _build_pair_envelope(
        app_state=app_state, pairing_key=key, plaintext=pt, device_id="fp_deadbeef"
    )
    resp = client.post("/api/public/pair", json=env)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "bad_envelope"


def test_pair_rejects_wrong_key_id(client: TestClient, app_state: AppState) -> None:
    key, _ = _current_pairing_key(app_state)
    phone = crypto.generate_x25519_keypair()
    pt = json.dumps({"client_pub": crypto.b64u_encode(phone.public_key)}).encode()
    env = _build_pair_envelope(app_state=app_state, pairing_key=key, plaintext=pt)
    env["key_id"] = "main"  # invalid for this endpoint
    resp = client.post("/api/public/pair", json=env)
    assert resp.status_code == 401


def test_pair_rejects_tampered_envelope(client: TestClient, app_state: AppState) -> None:
    key, _ = _current_pairing_key(app_state)
    phone = crypto.generate_x25519_keypair()
    pt = json.dumps({"client_pub": crypto.b64u_encode(phone.public_key)}).encode()
    env = _build_pair_envelope(app_state=app_state, pairing_key=key, plaintext=pt)
    # Flip a byte in ciphertext.
    ct = bytearray(crypto.b64u_decode(env["ciphertext"]))
    ct[0] ^= 0x01
    env["ciphertext"] = crypto.b64u_encode(bytes(ct))
    resp = client.post("/api/public/pair", json=env)
    assert resp.status_code == 401


def test_pair_attempt_limit_burns_secret(client: TestClient, app_state: AppState) -> None:
    key, _ = _current_pairing_key(app_state)
    # Build a deliberately broken envelope (good key, but cipher mangled).
    phone = crypto.generate_x25519_keypair()
    pt = json.dumps({"client_pub": crypto.b64u_encode(phone.public_key)}).encode()

    last_status_code: int = 0
    last_code: str = ""
    for _ in range(app_state.config.security.max_pairing_attempts):
        env = _build_pair_envelope(app_state=app_state, pairing_key=key, plaintext=pt)
        ct = bytearray(crypto.b64u_decode(env["ciphertext"]))
        ct[0] ^= 0x01
        env["ciphertext"] = crypto.b64u_encode(bytes(ct))
        resp = client.post("/api/public/pair", json=env)
        last_status_code = resp.status_code
        last_code = resp.json()["error"]["code"]

    assert last_status_code == 429
    assert last_code == "attempt_limit"
    # Pairing window should be gone.
    assert client.get("/api/public/pairing-status").json()["state"] == "unpaired"


def test_pair_rejects_after_window_expired(
    client: TestClient, app_state: AppState
) -> None:
    # Force the pairing window into the past by manipulating state directly.
    app_state.pairing._state.expires_at = 0  # noqa: SLF001 - test access
    key, _ = _current_pairing_key.__wrapped__(app_state) if hasattr(_current_pairing_key, "__wrapped__") else (None, None)  # type: ignore[assignment]
    # _current_pairing_key would raise PairingExpired; just hit the endpoint
    # with a stale envelope built before expiry.
    from flightpaper.security.pairing import PairingExpired

    with pytest.raises(PairingExpired):
        app_state.pairing.get_pairing_key()
    # Server should respond 410 on any pair attempt now.
    phone = crypto.generate_x25519_keypair()
    bogus_env = {
        "v": ENVELOPE_VERSION,
        "device_id": app_state.identity.device_id,
        "client_id": "iphone_aabbccddeeff",
        "key_id": "pairing",
        "seq": 0,
        "ts": 1_700_000_000,
        "nonce": crypto.b64u_encode(crypto.random_nonce()),
        "ciphertext": crypto.b64u_encode(b"X" * 32),
    }
    resp = client.post("/api/public/pair", json=bogus_env)
    assert resp.status_code == 410
    assert resp.json()["error"]["code"] == "pairing_expired"
