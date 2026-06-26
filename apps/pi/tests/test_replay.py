"""Tests for flightpaper.security.replay."""

from __future__ import annotations

import pytest

from flightpaper.security.replay import ReplayCheckResult, ReplayWindow


NOW = 1_700_000_000
CLIENT = "iphone_aaaaaaaaaaaa"


def _check(rw: ReplayWindow, *, seq: int, nonce: bytes, ts: int, now: int = NOW, baseline: int = 0) -> ReplayCheckResult:
    return rw.check(client_id=CLIENT, seq=seq, nonce=nonce, ts=ts, now=now, baseline_seq=baseline)


def test_first_message_passes() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    assert _check(rw, seq=1, nonce=b"n1", ts=NOW) == ReplayCheckResult.OK


def test_strict_monotonic_seq() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    rw.record(client_id=CLIENT, seq=5, nonce=b"n5")
    # Equal seq is a replay.
    assert _check(rw, seq=5, nonce=b"n5b", ts=NOW) == ReplayCheckResult.REPLAY_SEQ
    # Lower seq is a replay.
    assert _check(rw, seq=4, nonce=b"n4", ts=NOW) == ReplayCheckResult.REPLAY_SEQ
    # Higher seq passes.
    assert _check(rw, seq=6, nonce=b"n6", ts=NOW) == ReplayCheckResult.OK


def test_baseline_seq_floor() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    # Baseline acts as a floor even with no in-memory record (process restart).
    assert _check(rw, seq=10, nonce=b"n", ts=NOW, baseline=42) == ReplayCheckResult.REPLAY_SEQ
    assert _check(rw, seq=43, nonce=b"n", ts=NOW, baseline=42) == ReplayCheckResult.OK


def test_nonce_replay_detected() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    rw.record(client_id=CLIENT, seq=1, nonce=b"shared")
    # Higher seq but same nonce.
    assert _check(rw, seq=2, nonce=b"shared", ts=NOW) == ReplayCheckResult.REPLAY_NONCE


def test_expired_timestamp_past() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    assert _check(rw, seq=1, nonce=b"n", ts=NOW - 121) == ReplayCheckResult.EXPIRED


def test_expired_timestamp_future() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    assert _check(rw, seq=1, nonce=b"n", ts=NOW + 121) == ReplayCheckResult.EXPIRED


def test_per_client_isolation() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    rw.record(client_id="iphone_aaaaaaaaaaaa", seq=10, nonce=b"shared")
    # Same nonce / lower seq is fine for a different client.
    assert rw.check(
        client_id="iphone_bbbbbbbbbbbb",
        seq=1,
        nonce=b"shared",
        ts=NOW,
        now=NOW,
    ) == ReplayCheckResult.OK


def test_nonce_cache_lru_eviction() -> None:
    rw = ReplayWindow(replay_window_seconds=120, nonce_cache_size=3)
    for i in range(4):
        rw.record(client_id=CLIENT, seq=i + 1, nonce=f"n{i}".encode())
    # The oldest nonce (n0) was evicted; replaying it should not be flagged.
    assert _check(rw, seq=99, nonce=b"n0", ts=NOW) == ReplayCheckResult.OK
    # But n1, n2, n3 should still trip the nonce check.
    assert _check(rw, seq=99, nonce=b"n3", ts=NOW) == ReplayCheckResult.REPLAY_NONCE


def test_record_after_check_commit() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    # Verifier flow: check then record only on success.
    assert _check(rw, seq=1, nonce=b"n1", ts=NOW) == ReplayCheckResult.OK
    rw.record(client_id=CLIENT, seq=1, nonce=b"n1")
    assert _check(rw, seq=1, nonce=b"n1", ts=NOW) == ReplayCheckResult.REPLAY_SEQ


def test_reset_client() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    rw.record(client_id=CLIENT, seq=10, nonce=b"n")
    rw.reset_client(CLIENT)
    assert _check(rw, seq=1, nonce=b"n", ts=NOW) == ReplayCheckResult.OK


def test_clear_all() -> None:
    rw = ReplayWindow(replay_window_seconds=120)
    rw.record(client_id="iphone_aaaaaaaaaaaa", seq=5, nonce=b"n")
    rw.record(client_id="iphone_bbbbbbbbbbbb", seq=5, nonce=b"n")
    rw.clear()
    assert rw.check(client_id="iphone_aaaaaaaaaaaa", seq=1, nonce=b"x", ts=NOW, now=NOW) == ReplayCheckResult.OK


def test_invalid_construction() -> None:
    with pytest.raises(ValueError):
        ReplayWindow(replay_window_seconds=0)
    with pytest.raises(ValueError):
        ReplayWindow(replay_window_seconds=10, nonce_cache_size=0)
