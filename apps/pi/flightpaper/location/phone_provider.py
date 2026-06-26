"""Phone-supplied location: the API server hands updates to :meth:`update`.

This provider is threadsafe under a single internal lock because the
FastAPI request handler and the polling task both read it.
"""

from __future__ import annotations

from threading import Lock

from .models import Location


class PhoneProvider:
    """Holds the most recent location pushed by the paired iPhone."""

    source_name: str = "iphone"

    def __init__(self) -> None:
        self._lock = Lock()
        self._current: Location | None = None

    def current(self) -> Location | None:
        with self._lock:
            return self._current

    def update(self, location: Location) -> None:
        """Replace the current location.

        Callers (the API server) are expected to have already validated the
        payload via :func:`flightpaper.location.payload.validate_location_payload`.
        """

        with self._lock:
            self._current = location

    def clear(self) -> None:
        with self._lock:
            self._current = None


__all__ = ["PhoneProvider"]
