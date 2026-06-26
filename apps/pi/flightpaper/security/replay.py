"""Per-client replay protection: monotonic seq + nonce LRU + timestamp window.

A receiver MUST reject any envelope whose ``ts`` is more than
``replay_window_seconds`` outside its clock, whose ``seq`` is less than or
equal to the highest accepted ``seq`` for that client, or whose ``nonce``
has been seen recently for that client.

The window is in-memory: a process restart resets the per-client nonce
cache but the persisted ``last_seq_in`` in :class:`KeyStore` provides
durable monotonic protection for ``seq``.
"""

from __future__ import annotations

import enum
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock


class ReplayCheckResult(str, enum.Enum):
    OK = "ok"
    REPLAY_SEQ = "replay_seq"
    REPLAY_NONCE = "replay_nonce"
    EXPIRED = "expired"


@dataclass
class _ClientState:
    last_seq: int = 0
    nonces: OrderedDict[bytes, None] = field(default_factory=OrderedDict)


class ReplayWindow:
    def __init__(
        self,
        *,
        replay_window_seconds: int = 120,
        nonce_cache_size: int = 256,
    ) -> None:
        if replay_window_seconds <= 0:
            raise ValueError("replay_window_seconds must be > 0")
        if nonce_cache_size < 1:
            raise ValueError("nonce_cache_size must be >= 1")
        self._window_s = replay_window_seconds
        self._cache_size = nonce_cache_size
        self._lock = Lock()
        self._clients: dict[str, _ClientState] = {}

    # ------------------------------------------------------------------
    # Check + record
    # ------------------------------------------------------------------

    def check(
        self,
        *,
        client_id: str,
        seq: int,
        nonce: bytes,
        ts: int,
        now: int,
        baseline_seq: int = 0,
    ) -> ReplayCheckResult:
        """Determine whether an envelope is acceptable.

        ``baseline_seq`` is the durable lower bound for this client (use
        the persisted ``last_seq_in`` from :class:`KeyStore`); the check
        rejects ``seq`` not strictly greater than ``max(baseline_seq,
        in-memory last_seq)``.
        """

        if abs(now - ts) > self._window_s:
            return ReplayCheckResult.EXPIRED

        with self._lock:
            state = self._clients.get(client_id)
            last = max(state.last_seq if state else 0, baseline_seq)
            if seq <= last:
                return ReplayCheckResult.REPLAY_SEQ
            if state is not None and nonce in state.nonces:
                return ReplayCheckResult.REPLAY_NONCE

        return ReplayCheckResult.OK

    def record(self, *, client_id: str, seq: int, nonce: bytes) -> None:
        """Commit the (seq, nonce) for this client after the AEAD verifies."""

        with self._lock:
            state = self._clients.get(client_id)
            if state is None:
                state = _ClientState()
                self._clients[client_id] = state
            if seq > state.last_seq:
                state.last_seq = seq
            state.nonces[nonce] = None
            while len(state.nonces) > self._cache_size:
                state.nonces.popitem(last=False)

    def reset_client(self, client_id: str) -> None:
        with self._lock:
            self._clients.pop(client_id, None)

    def clear(self) -> None:
        with self._lock:
            self._clients.clear()


__all__ = ["ReplayCheckResult", "ReplayWindow"]
