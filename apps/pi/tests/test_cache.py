"""Tests for flightpaper.utils.cache."""

from __future__ import annotations

import time

from flightpaper.utils.cache import TTLCache


def test_set_get() -> None:
    c: TTLCache[str, int] = TTLCache(maxsize=4, ttl_seconds=60)
    c.set("a", 1)
    assert c.get("a") == 1
    assert c.get("missing") is None


def test_eviction_at_maxsize() -> None:
    c: TTLCache[int, int] = TTLCache(maxsize=3, ttl_seconds=60)
    c.set(1, 1)
    c.set(2, 2)
    c.set(3, 3)
    # Touch 1 so it becomes most-recent, then add 4 to evict 2.
    c.get(1)
    c.set(4, 4)
    assert c.get(1) == 1
    assert c.get(2) is None
    assert c.get(3) == 3
    assert c.get(4) == 4


def test_ttl_expiry() -> None:
    c: TTLCache[str, str] = TTLCache(maxsize=4, ttl_seconds=0.05)
    c.set("k", "v")
    assert c.get("k") == "v"
    time.sleep(0.08)
    assert c.get("k") is None


def test_contains_and_discard() -> None:
    c: TTLCache[str, int] = TTLCache(maxsize=4, ttl_seconds=60)
    c.set("a", 1)
    assert "a" in c
    c.discard("a")
    assert "a" not in c
    # Discarding missing key is fine.
    c.discard("missing")


def test_clear() -> None:
    c: TTLCache[int, int] = TTLCache(maxsize=4, ttl_seconds=60)
    c.set(1, 1)
    c.set(2, 2)
    c.clear()
    assert c.get(1) is None
    assert len(c) == 0
