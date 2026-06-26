"""High-level OpenSky polling: client + rate limiter + last-good cache.

:class:`OpenSkyProvider` is the object the rest of the Pi app talks to. The
display loop asks it for the current aircraft list; it never knows about
HTTP, OAuth tokens, or backoff.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..utils.geo import BoundingBox
from .client import OpenSkyClient, OpenSkyError, OpenSkyRateLimited, OpenSkyResponse
from .models import Aircraft, OpenSkyStates
from .rate_limit import RateLimiter

log = logging.getLogger(__name__)


@dataclass
class OpenSkyStatus:
    """Snapshot of the polling state, exposed via the API status endpoint."""

    last_status: str = "init"  # init | ok | stale | rate_limited | error | no_location
    last_update_age_seconds: int | None = None
    rate_limit_remaining: int | None = None
    last_error: str | None = None
    aircraft_count: int = 0


@dataclass
class OpenSkyProvider:
    client: OpenSkyClient
    limiter: RateLimiter
    cache_ttl_seconds: int = 120

    _last_response: OpenSkyResponse | None = field(default=None, init=False)
    _last_response_time: float | None = field(default=None, init=False)
    status: OpenSkyStatus = field(default_factory=OpenSkyStatus, init=False)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def can_poll_now(self) -> bool:
        return self.limiter.can_request_now()

    def fetch(self, *, bbox: BoundingBox, extended: bool = False) -> OpenSkyStates:
        """Fetch states from OpenSky, applying rate-limit backoff.

        On success: returns fresh aircraft and updates the cache.
        On rate-limit / network error: applies backoff and returns the cached
        states (marked stale via :attr:`status`). When no cache exists,
        returns an empty :class:`OpenSkyStates`.
        """

        if not self.limiter.can_request_now():
            log.debug(
                "skip poll: in backoff (%.1fs remaining)",
                self.limiter.seconds_until_next_allowed(),
            )
            self._refresh_age_and_maybe_mark_stale()
            return self._cached_or_empty()

        try:
            response = self.client.fetch_states(bbox=bbox, extended=extended)
        except OpenSkyRateLimited as exc:
            delay = self.limiter.on_rate_limited(retry_after_s=exc.retry_after_s)
            log.warning("opensky 429; backing off %.1fs", delay)
            self.status.last_status = "rate_limited"
            self.status.last_error = "rate_limited"
            return self._cached_or_empty()
        except OpenSkyError as exc:
            delay = self.limiter.on_network_error()
            log.warning("opensky error; backing off %.1fs: %s", delay, exc)
            self.status.last_status = "error"
            self.status.last_error = str(exc)[:120]
            return self._cached_or_empty()

        self.limiter.on_success(rate_limit_remaining=response.rate_limit_remaining)
        self._last_response = response
        self._last_response_time = self.limiter.time_fn()
        self.status.last_status = "ok"
        self.status.last_error = None
        self.status.rate_limit_remaining = response.rate_limit_remaining
        self.status.aircraft_count = response.states.count
        self.status.last_update_age_seconds = 0
        return response.states

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def cached_states(self) -> OpenSkyStates | None:
        return self._last_response.states if self._last_response else None

    def _cached_or_empty(self) -> OpenSkyStates:
        cached = self.cached_states()
        if cached is None:
            return OpenSkyStates(time=0, aircraft=[])
        return cached

    def _refresh_age_and_maybe_mark_stale(self) -> None:
        """Update ``last_update_age_seconds`` and promote ``ok → stale``.

        Called when we skip a poll due to backoff. Does not override
        more specific statuses like ``rate_limited`` or ``error``.
        """

        if self._last_response_time is None:
            return
        now = self.limiter.time_fn()
        age = max(0, int(now - self._last_response_time))
        self.status.last_update_age_seconds = age
        if age > self.cache_ttl_seconds and self.status.last_status == "ok":
            self.status.last_status = "stale"


__all__ = ["OpenSkyProvider", "OpenSkyStatus"]
