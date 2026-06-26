"""Rate-limit / backoff state machine for OpenSky calls.

The client itself stays simple: it asks the limiter whether it can fire a
request, runs the call, then reports the outcome back. The limiter applies:

* A configurable minimum interval between successful calls.
* A bounded exponential backoff with jitter on 429 / network failure.
* Optional reset based on the ``Retry-After`` header.

Time is read via an injectable ``time_fn`` so tests can drive the clock.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable

_DEFAULT_BACKOFF_MAX_S: float = 600.0


@dataclass
class RateLimiter:
    min_interval_s: float
    time_fn: Callable[[], float] = field(default=time.monotonic)
    backoff_initial_s: float = 5.0
    backoff_max_s: float = _DEFAULT_BACKOFF_MAX_S

    _next_allowed: float = field(default=0.0, init=False)
    _backoff_s: float = field(default=0.0, init=False)
    _last_remaining: int | None = field(default=None, init=False)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def can_request_now(self) -> bool:
        return self.time_fn() >= self._next_allowed

    def seconds_until_next_allowed(self) -> float:
        return max(0.0, self._next_allowed - self.time_fn())

    @property
    def rate_limit_remaining(self) -> int | None:
        return self._last_remaining

    # ------------------------------------------------------------------
    # Outcome reporting
    # ------------------------------------------------------------------

    def on_success(self, *, rate_limit_remaining: int | None = None) -> None:
        """Record a successful call; clear backoff."""

        self._backoff_s = 0.0
        self._last_remaining = rate_limit_remaining
        self._next_allowed = self.time_fn() + self.min_interval_s

    def on_rate_limited(self, *, retry_after_s: float | None = None) -> float:
        """Apply backoff after a 429. Returns the delay (seconds) applied."""

        delay = retry_after_s if retry_after_s is not None else self._next_backoff()
        self._next_allowed = self.time_fn() + delay
        return delay

    def on_network_error(self) -> float:
        """Apply backoff after a connection / timeout failure."""

        delay = self._next_backoff()
        self._next_allowed = self.time_fn() + delay
        return delay

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _next_backoff(self) -> float:
        if self._backoff_s <= 0:
            self._backoff_s = self.backoff_initial_s
        else:
            self._backoff_s = min(self.backoff_max_s, self._backoff_s * 2)
        # Full jitter: pick a random value in [0, current backoff]. Avoids
        # synchronized retries.
        return random.uniform(self._backoff_s * 0.5, self._backoff_s)


__all__ = ["RateLimiter"]
