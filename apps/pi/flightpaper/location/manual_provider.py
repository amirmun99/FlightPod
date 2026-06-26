"""Static manual location supplied by config or by the iPhone Settings screen.

Manual location is always-fresh by construction: each call to
:meth:`current` returns a fresh :class:`Location` stamped at ``now``. This
keeps the manager's freshness math uniform across providers and avoids
``"manual is somehow stale"`` confusion on the display.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Callable

from .models import Location


class ManualProvider:
    """A fixed lat/lon. Set ``enabled=False`` to disable without removing config."""

    source_name: str = "manual"

    def __init__(
        self,
        *,
        lat: float,
        lon: float,
        label: str = "Manual",
        enabled: bool = True,
        time_fn: Callable[[], int] = lambda: int(time.time()),
    ) -> None:
        self._lock = Lock()
        self._lat = lat
        self._lon = lon
        self._label = label or "Manual"
        self._enabled = enabled
        self._time_fn = time_fn

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled

    def update(self, *, lat: float, lon: float, label: str | None = None) -> None:
        """Replace the configured manual location (called from PATCH /config)."""

        with self._lock:
            self._lat = lat
            self._lon = lon
            if label is not None:
                self._label = label or "Manual"

    def current(self) -> Location | None:
        with self._lock:
            if not self._enabled:
                return None
            now = self._time_fn()
            return Location(
                lat=self._lat,
                lon=self._lon,
                accuracy_m=None,
                altitude_m=None,
                heading_deg=None,
                speed_mps=None,
                source=f"manual:{self._label}",
                timestamp=now,
                received_at=now,
            )


__all__ = ["ManualProvider"]
