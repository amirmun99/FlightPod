"""Tests for flightpaper.security.key_store."""

from __future__ import annotations

import stat
from pathlib import Path

from flightpaper.security.key_store import KeyStore, PairedClient


def _client(client_id: str = "iphone_aabbccddeeff") -> PairedClient:
    return PairedClient(
        client_id=client_id,
        client_public_key=b"\x11" * 32,
        session_key=b"\x22" * 32,
        paired_at=1_700_000_000,
        last_seen_at=None,
        last_seq_in=0,
        next_seq_out=1,
        app_instance_name="Amir's iPhone",
    )


def test_add_and_get(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    assert store.count() == 0
    store.add(_client())
    fetched = store.get("iphone_aabbccddeeff")
    assert fetched is not None
    assert fetched.app_instance_name == "Amir's iPhone"
    assert store.count() == 1


def test_persisted_file_secure(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    store.add(_client())
    path = tmp_path / "paired_clients.json"
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_round_trip_through_reload(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    store.add(_client())
    store.update_seq_in("iphone_aabbccddeeff", seq=42, now=1_700_000_500)
    store.claim_seq_out("iphone_aabbccddeeff")

    fresh = KeyStore(tmp_path)
    client = fresh.get("iphone_aabbccddeeff")
    assert client is not None
    assert client.last_seq_in == 42
    assert client.next_seq_out == 2
    assert client.last_seen_at == 1_700_000_500


def test_update_seq_in_monotonic(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    store.add(_client())
    store.update_seq_in("iphone_aabbccddeeff", seq=10)
    # Lower seq must not regress the counter.
    store.update_seq_in("iphone_aabbccddeeff", seq=5)
    client = store.get("iphone_aabbccddeeff")
    assert client is not None and client.last_seq_in == 10


def test_remove_and_clear(tmp_path: Path) -> None:
    store = KeyStore(tmp_path)
    store.add(_client("iphone_aaaaaaaaaaaa"))
    store.add(_client("iphone_bbbbbbbbbbbb"))
    assert store.remove("iphone_aaaaaaaaaaaa") is True
    assert store.remove("iphone_missingmissi") is False
    assert store.count() == 1
    store.clear()
    assert store.count() == 0
    assert KeyStore(tmp_path).count() == 0
