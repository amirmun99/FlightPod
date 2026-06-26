"""Tests for flightpaper.api.secure_envelope."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from flightpaper.api.secure_envelope import (
    EnvelopeSchemaError,
    EnvelopeVerificationError,
    build_aad,
    encrypt_envelope,
    open_envelope,
    seal_envelope,
)
from flightpaper.security.crypto import (
    b64u_decode,
    b64u_encode,
    derive_session_key,
    generate_x25519_keypair,
    x25519_shared_secret,
)
from flightpaper.security.key_store import KeyStore, PairedClient
from flightpaper.security.replay import ReplayWindow


DEVICE_ID = "fp_aabbccdd"
CLIENT_ID = "iphone_aabbccddeeff"
NOW = 1_700_000_000


def _make_session_key() -> bytes:
    pi = generate_x25519_keypair()
    phone = generate_x25519_keypair()
    shared = x25519_shared_secret(private_key=pi.private_key, peer_public_key=phone.public_key)
    return derive_session_key(
        shared_secret=shared,
        pairing_secret=b"\x42" * 32,
        device_id=DEVICE_ID,
        client_id=CLIENT_ID,
    )


def _make_store(tmp_path: Path, *, session_key: bytes) -> KeyStore:
    store = KeyStore(tmp_path)
    store.add(
        PairedClient(
            client_id=CLIENT_ID,
            client_public_key=b"\x11" * 32,
            session_key=session_key,
            paired_at=NOW - 600,
            last_seen_at=None,
            last_seq_in=0,
            next_seq_out=1,
        )
    )
    return store


def _seal(*, key: bytes, payload: dict[str, Any], seq: int = 1, ts: int = NOW) -> dict[str, Any]:
    return seal_envelope(
        payload=payload,
        key=key,
        method="POST",
        path="/api/secure/location",
        device_id=DEVICE_ID,
        client_id=CLIENT_ID,
        key_id="main",
        seq=seq,
        ts=ts,
    )


# ---------------------------------------------------------------------------
# AAD construction
# ---------------------------------------------------------------------------


def test_aad_layout_matches_spec() -> None:
    aad = build_aad(
        v=1,
        method="POST",
        path="/api/secure/x",
        device_id=DEVICE_ID,
        client_id=CLIENT_ID,
        key_id="main",
        seq=42,
        ts=NOW,
    )
    expected = (
        b"v=1|m=POST|p=/api/secure/x|d=" + DEVICE_ID.encode()
        + b"|c=" + CLIENT_ID.encode() + b"|k=main|s=42|t=" + str(NOW).encode()
    )
    assert aad == expected


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip(tmp_path: Path) -> None:
    key = _make_session_key()
    store = _make_store(tmp_path, session_key=key)
    replay = ReplayWindow(replay_window_seconds=120)

    envelope = _seal(key=key, payload={"lat": 43.3255, "lon": -79.7990, "ts": NOW})

    result = open_envelope(
        envelope,
        method="POST",
        path="/api/secure/location",
        key_store=store,
        replay=replay,
        now=NOW,
        expected_device_id=DEVICE_ID,
    )
    assert result.client.client_id == CLIENT_ID
    assert json.loads(result.plaintext.decode())["lat"] == 43.3255
    assert result.seq == 1


def test_replay_same_envelope_rejected(tmp_path: Path) -> None:
    key = _make_session_key()
    store = _make_store(tmp_path, session_key=key)
    replay = ReplayWindow(replay_window_seconds=120)
    envelope = _seal(key=key, payload={"x": 1})

    open_envelope(envelope, method="POST", path="/api/secure/location",
                  key_store=store, replay=replay, now=NOW)
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(envelope, method="POST", path="/api/secure/location",
                      key_store=store, replay=replay, now=NOW)
    assert exc.value.code == "replay"


def test_lower_seq_rejected_via_baseline(tmp_path: Path) -> None:
    key = _make_session_key()
    store = _make_store(tmp_path, session_key=key)
    replay = ReplayWindow(replay_window_seconds=120)

    # First, accept seq=10.
    env_high = _seal(key=key, payload={"x": "high"}, seq=10)
    open_envelope(env_high, method="POST", path="/api/secure/location",
                  key_store=store, replay=replay, now=NOW)

    # Then seq=5 must be rejected (baseline floor).
    env_low = _seal(key=key, payload={"x": "low"}, seq=5)
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(env_low, method="POST", path="/api/secure/location",
                      key_store=store, replay=replay, now=NOW)
    assert exc.value.code == "replay"


def test_expired_timestamp_rejected(tmp_path: Path) -> None:
    key = _make_session_key()
    store = _make_store(tmp_path, session_key=key)
    replay = ReplayWindow(replay_window_seconds=60)
    envelope = _seal(key=key, payload={"x": 1}, ts=NOW - 600)
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(envelope, method="POST", path="/api/secure/location",
                      key_store=store, replay=replay, now=NOW)
    assert exc.value.code == "expired"


# ---------------------------------------------------------------------------
# Cryptographic tamper resistance
# ---------------------------------------------------------------------------


def test_tampered_ciphertext_rejected(tmp_path: Path) -> None:
    key = _make_session_key()
    store = _make_store(tmp_path, session_key=key)
    replay = ReplayWindow(replay_window_seconds=120)
    envelope = _seal(key=key, payload={"x": 1})
    bad = bytearray(b64u_decode(envelope["ciphertext"]))
    bad[0] ^= 0x01
    envelope["ciphertext"] = b64u_encode(bytes(bad))
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(envelope, method="POST", path="/api/secure/location",
                      key_store=store, replay=replay, now=NOW)
    assert exc.value.code == "bad_envelope"


def test_wrong_method_rejected(tmp_path: Path) -> None:
    key = _make_session_key()
    store = _make_store(tmp_path, session_key=key)
    replay = ReplayWindow(replay_window_seconds=120)
    envelope = _seal(key=key, payload={"x": 1})
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(envelope, method="GET", path="/api/secure/location",
                      key_store=store, replay=replay, now=NOW)
    assert exc.value.code == "bad_envelope"


def test_wrong_path_rejected(tmp_path: Path) -> None:
    key = _make_session_key()
    store = _make_store(tmp_path, session_key=key)
    replay = ReplayWindow(replay_window_seconds=120)
    envelope = _seal(key=key, payload={"x": 1})
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(envelope, method="POST", path="/api/secure/refresh",
                      key_store=store, replay=replay, now=NOW)
    assert exc.value.code == "bad_envelope"


def test_swapped_session_key_rejected(tmp_path: Path) -> None:
    # Build an envelope under one key, but the store holds a different key.
    key_a = _make_session_key()
    key_b = _make_session_key()
    assert key_a != key_b
    store = _make_store(tmp_path, session_key=key_b)
    replay = ReplayWindow(replay_window_seconds=120)
    envelope = _seal(key=key_a, payload={"x": 1})
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(envelope, method="POST", path="/api/secure/location",
                      key_store=store, replay=replay, now=NOW)
    assert exc.value.code == "bad_envelope"


def test_unknown_client_rejected(tmp_path: Path) -> None:
    key = _make_session_key()
    store = KeyStore(tmp_path)  # empty
    replay = ReplayWindow(replay_window_seconds=120)
    envelope = _seal(key=key, payload={"x": 1})
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(envelope, method="POST", path="/api/secure/location",
                      key_store=store, replay=replay, now=NOW)
    assert exc.value.code == "not_paired"


def test_device_id_mismatch_rejected(tmp_path: Path) -> None:
    key = _make_session_key()
    store = _make_store(tmp_path, session_key=key)
    replay = ReplayWindow(replay_window_seconds=120)
    envelope = _seal(key=key, payload={"x": 1})
    with pytest.raises(EnvelopeVerificationError) as exc:
        open_envelope(envelope, method="POST", path="/api/secure/location",
                      key_store=store, replay=replay, now=NOW,
                      expected_device_id="fp_deadbeef")
    assert exc.value.code == "bad_envelope"


# ---------------------------------------------------------------------------
# Schema rejection (pre-crypto)
# ---------------------------------------------------------------------------


class TestSchemaRejection:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path) -> None:
        self.key = _make_session_key()
        self.store = _make_store(tmp_path, session_key=self.key)
        self.replay = ReplayWindow(replay_window_seconds=120)

    def _open(self, env: dict[str, Any]) -> Any:
        return open_envelope(
            env,
            method="POST",
            path="/api/secure/location",
            key_store=self.store,
            replay=self.replay,
            now=NOW,
        )

    def _baseline(self) -> dict[str, Any]:
        return _seal(key=self.key, payload={"x": 1})

    def test_missing_v(self) -> None:
        env = self._baseline()
        del env["v"]
        with pytest.raises(EnvelopeSchemaError):
            self._open(env)

    def test_wrong_version(self) -> None:
        env = self._baseline()
        env["v"] = 2
        with pytest.raises(EnvelopeSchemaError):
            self._open(env)

    def test_bad_device_id_pattern(self) -> None:
        env = self._baseline()
        env["device_id"] = "fp_NOT_HEX"
        with pytest.raises(EnvelopeSchemaError):
            self._open(env)

    def test_bad_client_id_pattern(self) -> None:
        env = self._baseline()
        env["client_id"] = "android_aabbccddeeff"
        with pytest.raises(EnvelopeSchemaError):
            self._open(env)

    def test_negative_seq(self) -> None:
        env = self._baseline()
        env["seq"] = -1
        with pytest.raises(EnvelopeSchemaError):
            self._open(env)

    def test_invalid_key_id(self) -> None:
        env = self._baseline()
        env["key_id"] = "bogus"
        with pytest.raises(EnvelopeSchemaError):
            self._open(env)

    def test_pairing_key_id_rejected_by_open(self) -> None:
        env = self._baseline()
        env["key_id"] = "pairing"
        with pytest.raises(EnvelopeSchemaError):
            self._open(env)

    def test_invalid_nonce_length(self) -> None:
        env = self._baseline()
        env["nonce"] = b64u_encode(b"\x00" * 12)  # not 24
        with pytest.raises(EnvelopeSchemaError):
            self._open(env)


# ---------------------------------------------------------------------------
# Encrypt helper
# ---------------------------------------------------------------------------


def test_encrypt_envelope_inserts_random_nonce() -> None:
    key = _make_session_key()
    e1 = encrypt_envelope(
        plaintext=b"hello",
        key=key,
        method="POST",
        path="/x",
        device_id=DEVICE_ID,
        client_id=CLIENT_ID,
        key_id="main",
        seq=1,
        ts=NOW,
    )
    e2 = encrypt_envelope(
        plaintext=b"hello",
        key=key,
        method="POST",
        path="/x",
        device_id=DEVICE_ID,
        client_id=CLIENT_ID,
        key_id="main",
        seq=1,
        ts=NOW,
    )
    assert e1["nonce"] != e2["nonce"]
    assert e1["ciphertext"] != e2["ciphertext"]
