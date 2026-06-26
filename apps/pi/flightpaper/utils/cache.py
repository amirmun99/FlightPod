"""Small in-memory caches used by the OpenSky client and replay window."""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    """Tiny LRU+TTL cache. Threadsafe under a single lock; not designed for
    high contention. Used for: OpenSky response cache, replay nonce window.
    """

    def __init__(self, *, maxsize: int = 256, ttl_seconds: float = 60.0) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._items: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def __len__(self) -> int:
        with self._lock:
            self._evict_expired_locked(time.monotonic())
            return len(self._items)

    def __contains__(self, key: K) -> bool:
        return self.get(key) is not None

    def get(self, key: K) -> V | None:
        with self._lock:
            now = time.monotonic()
            self._evict_expired_locked(now)
            entry = self._items.get(key)
            if entry is None:
                return None
            self._items.move_to_end(key)
            return entry[1]

    def set(self, key: K, value: V) -> None:
        with self._lock:
            now = time.monotonic()
            self._evict_expired_locked(now)
            self._items[key] = (now + self._ttl, value)
            self._items.move_to_end(key)
            while len(self._items) > self._maxsize:
                self._items.popitem(last=False)

    def discard(self, key: K) -> None:
        with self._lock:
            self._items.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def _evict_expired_locked(self, now: float) -> None:
        # OrderedDict insertion order != expiry order in general, but we
        # set TTL uniformly, so insertion order is expiry order.
        while self._items:
            oldest_key, (expiry, _) = next(iter(self._items.items()))
            if expiry > now:
                return
            self._items.pop(oldest_key, None)


__all__ = ["TTLCache"]
