"""Typed Location model + freshness enum + payload shape.

The :class:`Location` is the *internal* representation persisted by the
:class:`flightpaper.location.manager.LocationManager`. The
:class:`LocationPayload` is the *external* shape the iPhone sends; see
``packages/protocol/api-contract.md`` for the JSON wire format.

We keep them distinct so the manager can hold derived fields
(``received_at``) that the wire payload doesn't include.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


@dataclass(frozen=True)
class Location:
    """Internal representation of a user's location."""

    lat: float
    lon: float
    accuracy_m: float | None
    altitude_m: float | None
    heading_deg: float | None
    speed_mps: float | None
    source: str
    timestamp: int        # sender's unix seconds
    received_at: int      # Pi's unix seconds when this was accepted

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LocationPayload:
    """Validated subset of fields the phone is allowed to send.

    Construct with :func:`flightpaper.location.payload.validate_location_payload`,
    not directly.
    """

    lat: float
    lon: float
    accuracy_m: float | None
    altitude_m: float | None
    heading_deg: float | None
    speed_mps: float | None
    source: str
    timestamp: int


class Freshness(str, Enum):
    """Bucketized age of the current location."""

    NONE = "none"
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"


class InvalidLocationPayload(ValueError):
    """Raised by the payload validator."""


__all__ = [
    "Freshness",
    "InvalidLocationPayload",
    "Location",
    "LocationPayload",
]
