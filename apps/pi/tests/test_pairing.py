"""Tests for flightpaper.security.pairing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flightpaper.security import crypto
from flightpaper.security.device_identity import (
    DeviceIdentity,
    load_or_create_identity,
)
from flightpaper.security.key_store import KeyStore
from flightpaper.security.pairing import (
    PairingExpired,
    PairingManager,
    PairingStatus,
    build_pair_uri,
    parse_pair_uri,
)
from flightpaper.security.replay import ReplayWindow


class Clock:
    def __init__(self, t: int = 1_700_000_000) -> None:
        self.t = t

    def __call__(self) -> int:
        return self.t

    def advance(self, dt: int) -> None:
        self.t += dt


def _make_manager(tmp: Path, *, clock: Clock | None = None) -> PairingManager:
    clock = clock or Clock()
    identity = load_or_create_identity(tmp, device_name="FlightPaper")
    store = KeyStore(tmp)
    return PairingManager(
        secure_dir=tmp,
        identity=identity,
        key_store=store,
        replay=ReplayWindow(replay_window_seconds=120),
        host_provider=lambda: ("172.20.10.4", 8080),
        expires_seconds=600,
        max_attempts=3,
        time_fn=clock,
    )


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


def test_fresh_device_is_unpaired(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    status = mgr.status()
    assert status["state"] == PairingStatus.UNPAIRED.value
    assert status["device_id"].startswith("fp_")


def test_start_transitions_to_pending(tmp_path: Path) -> None:
    clock = Clock()
    mgr = _make_manager(tmp_path, clock=clock)
    state = mgr.start()
    assert state.status == PairingStatus.PAIRING_PENDING
    assert state.pairing_secret is not None and len(state.pairing_secret) == 32
    assert state.expires_at == clock.t + 600
    assert mgr.status()["state"] == "pairing_pending"


def test_qr_payload_contains_required_fields(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    mgr.start()
    payload = mgr.qr_payload()
    for required in ("v", "host", "port", "device_id", "device_name", "device_pub", "pairing_secret", "expires_at", "code"):
        assert required in payload
    # device_pub and pairing_secret are base64url-encoded 32-byte values.
    assert len(crypto.b64u_decode(payload["device_pub"])) == 32
    assert len(crypto.b64u_decode(payload["pairing_secret"])) == 32
    assert payload["code"].count("-") == 1


def test_qr_uri_is_parseable(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    mgr.start()
    uri = mgr.qr_uri()
    assert uri.startswith("flightpaper://pair?p=")
    decoded = parse_pair_uri(uri)
    assert decoded["device_id"] == mgr.status()["device_id"]


def test_build_and_parse_pair_uri_round_trip() -> None:
    payload = {
        "v": 1,
        "host": "172.20.10.4",
        "port": 8080,
        "device_id": "fp_aabbccdd",
        "device_name": "FlightPaper",
        "device_pub": crypto.b64u_encode(b"\x11" * 32),
        "pairing_secret": crypto.b64u_encode(b"\x22" * 32),
        "expires_at": 1_700_000_600,
        "code": "123-456",
    }
    uri = build_pair_uri(payload)
    assert parse_pair_uri(uri) == payload


def test_parse_pair_uri_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_pair_uri("https://example.com/?p=xxx")
    with pytest.raises(ValueError):
        parse_pair_uri("flightpaper://pair?q=x")
    with pytest.raises(ValueError):
        parse_pair_uri("flightpaper://pair?p=not-base64!!!")


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------


def test_complete_pair_with_valid_phone_keypair(tmp_path: Path) -> None:
    clock = Clock()
    mgr = _make_manager(tmp_path, clock=clock)
    mgr.start()

    phone = crypto.generate_x25519_keypair()
    client = mgr.complete(
        client_id="iphone_aabbccddeeff",
        client_public_key=phone.public_key,
        app_instance_name="Amir's iPhone",
    )

    assert client.client_id == "iphone_aabbccddeeff"
    assert client.session_key
    assert client.app_instance_name == "Amir's iPhone"
    assert mgr.status()["state"] == "paired"


def test_handshake_secret_consumed_on_complete(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    mgr.start()
    phone = crypto.generate_x25519_keypair()
    mgr.complete(client_id="iphone_aabbccddeeff", client_public_key=phone.public_key)

    # A second complete should fail because the pairing window is closed.
    with pytest.raises(PairingExpired):
        mgr.complete(client_id="iphone_bbbbbbbbbbbb", client_public_key=phone.public_key)


def test_complete_without_start_rejects(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    phone = crypto.generate_x25519_keypair()
    with pytest.raises(PairingExpired):
        mgr.complete(client_id="iphone_aabbccddeeff", client_public_key=phone.public_key)


def test_expired_window_rejects(tmp_path: Path) -> None:
    clock = Clock()
    mgr = _make_manager(tmp_path, clock=clock)
    mgr.start()
    clock.advance(601)  # past 600-second window
    phone = crypto.generate_x25519_keypair()
    with pytest.raises(PairingExpired):
        mgr.complete(client_id="iphone_aabbccddeeff", client_public_key=phone.public_key)


def test_expired_window_visible_in_status(tmp_path: Path) -> None:
    clock = Clock()
    mgr = _make_manager(tmp_path, clock=clock)
    mgr.start()
    clock.advance(601)
    status = mgr.status()
    assert status["state"] == "unpaired"


# ---------------------------------------------------------------------------
# Attempt limiter
# ---------------------------------------------------------------------------


def test_attempt_limit_kills_secret(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    mgr.start()

    # max_attempts in helper is 3; after 3 failures the secret is gone.
    assert mgr.record_attempt_failure() is False
    assert mgr.record_attempt_failure() is False
    assert mgr.record_attempt_failure() is True
    assert mgr.status()["state"] == "unpaired"

    phone = crypto.generate_x25519_keypair()
    with pytest.raises(PairingExpired):
        mgr.complete(client_id="iphone_aabbccddeeff", client_public_key=phone.public_key)


# ---------------------------------------------------------------------------
# Reset + persistence
# ---------------------------------------------------------------------------


def test_reset_clears_clients_and_pending_state(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    mgr.start()
    phone = crypto.generate_x25519_keypair()
    mgr.complete(client_id="iphone_aabbccddeeff", client_public_key=phone.public_key)
    assert mgr.is_paired()

    mgr.reset()
    assert mgr.status()["state"] == "unpaired"
    # Pairing state file should reflect unpaired status on reload.
    raw = json.loads((tmp_path / "pairing_state.json").read_text())
    assert raw["status"] == "unpaired"
    assert raw["pairing_secret"] is None


def test_state_persists_across_restart(tmp_path: Path) -> None:
    clock = Clock()
    mgr = _make_manager(tmp_path, clock=clock)
    mgr.start()
    phone = crypto.generate_x25519_keypair()
    mgr.complete(client_id="iphone_aabbccddeeff", client_public_key=phone.public_key)

    fresh_clock = Clock(t=clock.t + 10)
    fresh = _make_manager(tmp_path, clock=fresh_clock)
    assert fresh.status()["state"] == "paired"


# ---------------------------------------------------------------------------
# Shared-secret agreement (the actual handshake math)
# ---------------------------------------------------------------------------


def test_phone_and_pi_derive_same_session_key(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path)
    state = mgr.start()
    payload = mgr.qr_payload()
    pairing_secret = crypto.b64u_decode(payload["pairing_secret"])
    device_pub = crypto.b64u_decode(payload["device_pub"])

    # Phone-side derivation.
    phone = crypto.generate_x25519_keypair()
    phone_shared = crypto.x25519_shared_secret(
        private_key=phone.private_key,
        peer_public_key=device_pub,
    )
    phone_session_key = crypto.derive_session_key(
        shared_secret=phone_shared,
        pairing_secret=pairing_secret,
        device_id=payload["device_id"],
        client_id="iphone_aabbccddeeff",
    )

    # Pi-side derivation (via PairingManager.complete).
    pi_client = mgr.complete(client_id="iphone_aabbccddeeff", client_public_key=phone.public_key)

    assert phone_session_key == pi_client.session_key
