"""Sanity checks shared by the location API and the OpenSky parser."""

from __future__ import annotations

# Reasonable far-future tolerance for inbound timestamps, in seconds. The
# phone and Pi clocks can drift, especially before NTP kicks in.
_FUTURE_SKEW_S = 5 * 60
_PAST_SKEW_S = 24 * 3600


def is_valid_lat(lat: float | None) -> bool:
    return isinstance(lat, (int, float)) and -90.0 <= float(lat) <= 90.0


def is_valid_lon(lon: float | None) -> bool:
    return isinstance(lon, (int, float)) and -180.0 <= float(lon) <= 180.0


def is_reasonable_accuracy(meters: float | None) -> bool:
    """Accept ``None`` (unknown) or non-negative and < 10 km."""

    if meters is None:
        return True
    return isinstance(meters, (int, float)) and 0.0 <= float(meters) <= 10_000.0


def is_reasonable_timestamp(ts: int | float | None, *, now: int) -> bool:
    """Accept timestamps within a forgiving past and future window of ``now``."""

    if ts is None:
        return False
    try:
        t = float(ts)
    except (TypeError, ValueError):
        return False
    return (now - _PAST_SKEW_S) <= t <= (now + _FUTURE_SKEW_S)


def is_reasonable_altitude_m(m: float | None) -> bool:
    """Accept ``None`` or values that aren't obviously impossible for civil aviation."""

    if m is None:
        return True
    return isinstance(m, (int, float)) and -500.0 <= float(m) <= 20_000.0


def is_reasonable_velocity_mps(v: float | None) -> bool:
    if v is None:
        return True
    return isinstance(v, (int, float)) and 0.0 <= float(v) <= 700.0  # ~Mach 2


def is_reasonable_track_deg(deg: float | None) -> bool:
    if deg is None:
        return True
    return isinstance(deg, (int, float)) and 0.0 <= float(deg) < 360.0


__all__ = [
    "is_valid_lat",
    "is_valid_lon",
    "is_reasonable_accuracy",
    "is_reasonable_timestamp",
    "is_reasonable_altitude_m",
    "is_reasonable_velocity_mps",
    "is_reasonable_track_deg",
]
