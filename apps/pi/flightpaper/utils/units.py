"""Unit conversions used by the aircraft pipeline and rendering."""

from __future__ import annotations

_METERS_PER_FOOT = 0.3048
_METERS_PER_NAUTICAL_MILE = 1852.0
_KNOTS_PER_MPS = 1.9438444924406046  # 3600 / 1852
_FPM_PER_MPS = 196.85039370078738  # 60 / 0.3048


def meters_to_feet(m: float | None) -> float | None:
    return None if m is None else m / _METERS_PER_FOOT


def feet_to_meters(ft: float | None) -> float | None:
    return None if ft is None else ft * _METERS_PER_FOOT


def mps_to_knots(mps: float | None) -> float | None:
    return None if mps is None else mps * _KNOTS_PER_MPS


def knots_to_mps(kt: float | None) -> float | None:
    return None if kt is None else kt / _KNOTS_PER_MPS


def km_to_nm(km: float | None) -> float | None:
    return None if km is None else km * 1000.0 / _METERS_PER_NAUTICAL_MILE


def nm_to_km(nm: float | None) -> float | None:
    return None if nm is None else nm * _METERS_PER_NAUTICAL_MILE / 1000.0


def mps_to_fpm(mps: float | None) -> float | None:
    """Vertical speed: meters per second to feet per minute."""

    return None if mps is None else mps * _FPM_PER_MPS


def mps_to_kmh(mps: float | None) -> float | None:
    return None if mps is None else mps * 3.6


__all__ = [
    "meters_to_feet",
    "feet_to_meters",
    "mps_to_knots",
    "knots_to_mps",
    "km_to_nm",
    "nm_to_km",
    "mps_to_fpm",
    "mps_to_kmh",
]
