"""Typed models for OpenSky state vectors and the FlightPaper Aircraft model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Aircraft:
    """One aircraft as FlightPaper understands it.

    Fields up to ``category`` mirror the OpenSky state-vector layout in
    spec §14. The trailing three fields (``distance_km``, ``bearing_deg``,
    ``age_seconds``) are derived by :mod:`flightpaper.aircraft.processor`.
    """

    icao24: str
    callsign: str | None = None
    origin_country: str | None = None
    time_position: int | None = None
    last_contact: int | None = None
    longitude: float | None = None
    latitude: float | None = None
    baro_altitude_m: float | None = None
    on_ground: bool = False
    velocity_mps: float | None = None
    true_track_deg: float | None = None
    vertical_rate_mps: float | None = None
    geo_altitude_m: float | None = None
    squawk: str | None = None
    spi: bool | None = None
    position_source: int | None = None
    category: int | None = None

    # Derived fields populated by the processor.
    distance_km: float | None = None
    bearing_deg: float | None = None
    age_seconds: int | None = None


@dataclass
class OpenSkyStates:
    """Parsed OpenSky ``/states/all`` response."""

    time: int
    aircraft: list[Aircraft] = field(default_factory=list)
    # Optional metadata read from response headers.
    rate_limit_remaining: int | None = None

    @property
    def count(self) -> int:
        return len(self.aircraft)


# ---------------------------------------------------------------------------
# OpenSky state-vector positional indexes
# ---------------------------------------------------------------------------
#
# The API returns each aircraft as a positional list. Indexing by name keeps
# the parser readable. Reference:
# https://openskynetwork.github.io/opensky-api/rest.html#response

STATE_VECTOR_INDEXES: dict[str, int] = {
    "icao24": 0,
    "callsign": 1,
    "origin_country": 2,
    "time_position": 3,
    "last_contact": 4,
    "longitude": 5,
    "latitude": 6,
    "baro_altitude_m": 7,
    "on_ground": 8,
    "velocity_mps": 9,
    "true_track_deg": 10,
    "vertical_rate_mps": 11,
    "sensors": 12,
    "geo_altitude_m": 13,
    "squawk": 14,
    "spi": 15,
    "position_source": 16,
    # Only present when extended=1 was requested.
    "category": 17,
}


def state_vector_field(row: list[Any], name: str) -> Any:
    """Read a named OpenSky state-vector field, returning ``None`` if missing."""

    idx = STATE_VECTOR_INDEXES.get(name)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


__all__ = [
    "Aircraft",
    "OpenSkyStates",
    "STATE_VECTOR_INDEXES",
    "state_vector_field",
]
