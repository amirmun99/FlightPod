"""Strict validator for inbound location payloads.

Phase 5's API server will define a Pydantic schema, but the deeper sanity
checks (lat/lon ranges, accuracy plausibility, timestamp drift, allowed
sources) live here so they can be exercised by tests and reused by
non-HTTP entry points (scripts, manual injection).
"""

from __future__ import annotations

from typing import Any, Mapping

from ..utils.validators import (
    is_reasonable_accuracy,
    is_reasonable_altitude_m,
    is_reasonable_timestamp,
    is_reasonable_track_deg,
    is_reasonable_velocity_mps,
    is_valid_lat,
    is_valid_lon,
)
from .models import InvalidLocationPayload, LocationPayload

# The iPhone app sets ``source`` to one of these per the API contract.
_ALLOWED_SOURCES: frozenset[str] = frozenset(
    {"iphone_foreground", "iphone_background"}
)


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidLocationPayload(f"expected number, got {type(value).__name__}") from exc


def validate_location_payload(raw: Mapping[str, Any], *, now: int) -> LocationPayload:
    """Validate one location payload and return an immutable :class:`LocationPayload`.

    Raises :class:`InvalidLocationPayload` with a short human reason on the
    first failed check. The reason string is safe to log (no payload values).
    """

    if not isinstance(raw, Mapping):
        raise InvalidLocationPayload("payload must be a JSON object")

    # ---- Required fields -------------------------------------------------
    for required in ("lat", "lon", "timestamp", "source"):
        if required not in raw:
            raise InvalidLocationPayload(f"missing field: {required}")

    lat = _opt_float(raw["lat"])
    lon = _opt_float(raw["lon"])
    if lat is None or not is_valid_lat(lat):
        raise InvalidLocationPayload("lat out of range")
    if lon is None or not is_valid_lon(lon):
        raise InvalidLocationPayload("lon out of range")

    try:
        timestamp = int(raw["timestamp"])
    except (TypeError, ValueError) as exc:
        raise InvalidLocationPayload("timestamp must be an integer") from exc
    if not is_reasonable_timestamp(timestamp, now=now):
        raise InvalidLocationPayload("timestamp out of acceptable range")

    source = raw["source"]
    if not isinstance(source, str) or source not in _ALLOWED_SOURCES:
        raise InvalidLocationPayload("source not allowed")

    # ---- Optional fields -------------------------------------------------
    accuracy_m = _opt_float(raw.get("accuracy_m"))
    if not is_reasonable_accuracy(accuracy_m):
        raise InvalidLocationPayload("accuracy_m out of range")

    altitude_m = _opt_float(raw.get("altitude_m"))
    if not is_reasonable_altitude_m(altitude_m):
        raise InvalidLocationPayload("altitude_m out of range")

    heading_deg = _opt_float(raw.get("heading_deg"))
    if not is_reasonable_track_deg(heading_deg):
        raise InvalidLocationPayload("heading_deg out of range")

    speed_mps = _opt_float(raw.get("speed_mps"))
    if not is_reasonable_velocity_mps(speed_mps):
        raise InvalidLocationPayload("speed_mps out of range")

    return LocationPayload(
        lat=lat,
        lon=lon,
        accuracy_m=accuracy_m,
        altitude_m=altitude_m,
        heading_deg=heading_deg,
        speed_mps=speed_mps,
        source=source,
        timestamp=timestamp,
    )


__all__ = ["validate_location_payload"]
