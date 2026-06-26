"""Compose phone + manual providers and expose freshness state.

The manager is the single read point for the rest of the Pi app:

* Polling loop calls :meth:`usable_for_polling` to decide whether to query OpenSky.
* Status endpoint calls :meth:`status_dict` to produce the ``location`` block.
* Renderer calls :meth:`current` and :meth:`age_seconds` for the status bar.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Literal

from .models import Freshness, Location, LocationPayload
from .manual_provider import ManualProvider
from .phone_provider import PhoneProvider

log = logging.getLogger(__name__)

PrimarySource = Literal["iphone", "manual"]


class LocationManager:
    """Compose providers and answer "where is the user, and how old is that?".

    Parameters
    ----------
    phone, manual:
        Concrete providers. ``manual`` may be ``None`` if not configured.
    primary_source:
        ``"iphone"`` (default) prefers the phone-supplied fix; falls back to
        manual when the phone has none. ``"manual"`` always uses manual when
        enabled, regardless of phone state.
    stale_warning_seconds, expired_seconds:
        Thresholds from spec §15 (``900`` / ``3600``).
    """

    def __init__(
        self,
        *,
        phone: PhoneProvider,
        manual: ManualProvider | None = None,
        primary_source: PrimarySource = "iphone",
        stale_warning_seconds: int = 900,
        expired_seconds: int = 3600,
        time_fn: Callable[[], int] = lambda: int(time.time()),
    ) -> None:
        if stale_warning_seconds <= 0 or expired_seconds <= 0:
            raise ValueError("thresholds must be positive")
        if expired_seconds < stale_warning_seconds:
            raise ValueError("expired_seconds must be >= stale_warning_seconds")
        self._phone = phone
        self._manual = manual
        self._primary = primary_source
        self._stale_s = stale_warning_seconds
        self._expired_s = expired_seconds
        self._time_fn = time_fn

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def current(self) -> Location | None:
        if self._primary == "manual" and self._manual is not None:
            return self._manual.current() or self._phone.current()
        # Phone takes priority; fall back to manual when phone is empty.
        return self._phone.current() or (
            self._manual.current() if self._manual is not None else None
        )

    def age_seconds(self) -> int | None:
        loc = self.current()
        if loc is None:
            return None
        return max(0, self._time_fn() - loc.timestamp)

    def freshness(self) -> Freshness:
        age = self.age_seconds()
        if age is None:
            return Freshness.NONE
        if age <= self._stale_s:
            return Freshness.FRESH
        if age <= self._expired_s:
            return Freshness.STALE
        return Freshness.EXPIRED

    def usable_for_polling(self) -> Location | None:
        """Return the current location iff it's good enough to query OpenSky."""

        loc = self.current()
        if loc is None:
            return None
        if self.freshness() == Freshness.EXPIRED:
            return None
        return loc

    def status_dict(self) -> dict:
        """Block matching the ``location`` section of ``/api/secure/status``."""

        loc = self.current()
        freshness = self.freshness()
        if loc is None:
            return {
                "source": None,
                "age_seconds": None,
                "accuracy_m": None,
                "fresh": False,
                "state": Freshness.NONE.value,
            }
        return {
            "source": loc.source,
            "age_seconds": self.age_seconds(),
            "accuracy_m": loc.accuracy_m,
            "fresh": freshness == Freshness.FRESH,
            "state": freshness.value,
        }

    # ------------------------------------------------------------------
    # Write API (used by the API server and config-PATCH handler)
    # ------------------------------------------------------------------

    def apply_phone_payload(self, payload: LocationPayload, *, now: int) -> Location:
        """Convert a validated payload to a stored :class:`Location`."""

        loc = Location(
            lat=payload.lat,
            lon=payload.lon,
            accuracy_m=payload.accuracy_m,
            altitude_m=payload.altitude_m,
            heading_deg=payload.heading_deg,
            speed_mps=payload.speed_mps,
            source=payload.source,
            timestamp=payload.timestamp,
            received_at=now,
        )
        self._phone.update(loc)
        log.debug(
            "phone location accepted: source=%s age=%ss accuracy=%sm",
            loc.source,
            now - loc.timestamp,
            loc.accuracy_m,
        )
        return loc

    def set_primary_source(self, primary: PrimarySource) -> None:
        if primary not in ("iphone", "manual"):
            raise ValueError("primary_source must be 'iphone' or 'manual'")
        self._primary = primary


__all__ = ["LocationManager", "PrimarySource"]
