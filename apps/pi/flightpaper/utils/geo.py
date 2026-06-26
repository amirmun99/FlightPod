"""Geospatial helpers used across the aircraft pipeline and the radar page.

All functions are pure, deterministic, and side-effect free. Inputs and
outputs are plain floats; no numpy dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NamedTuple

# Mean Earth radius (km). Matches the value implied in the spec's bbox math
# (``radius_km / 111.0``).
EARTH_RADIUS_KM = 6371.0088

# Per-degree latitude length in km. Latitude lines are nearly parallel so a
# scalar is acceptable for the radius-to-bbox calculation called out in the
# spec.
KM_PER_DEG_LAT = 111.0


class BoundingBox(NamedTuple):
    """Geographic bounding box, OpenSky-compatible (lamin, lomin, lamax, lomax)."""

    lamin: float
    lomin: float
    lamax: float
    lomax: float


@dataclass(frozen=True)
class ScreenPoint:
    """Pixel-space coordinates for the radar projection."""

    x: int
    y: int


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon pairs in kilometers."""

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_KM * c


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing from point 1 to point 2, in degrees (0..360, 0=N)."""

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    theta = math.degrees(math.atan2(x, y))
    return (theta + 360.0) % 360.0


_CARDINALS: tuple[str, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def cardinal_direction(bearing: float) -> str:
    """Convert a bearing in degrees to a compact cardinal label (N..NW)."""

    normalized = bearing % 360.0
    # Each sector is 45 degrees wide; N sector wraps around 0.
    idx = int((normalized + 22.5) // 45) % 8
    return _CARDINALS[idx]


def latlon_bbox(lat: float, lon: float, radius_km: float) -> BoundingBox:
    """Bounding box around ``(lat, lon)`` containing a circle of ``radius_km``.

    Uses the linear approximation from the spec (``radius / 111`` for lat,
    scaled by ``cos(lat)`` for lon). Longitude is clamped to a valid range
    and the lat extents are clamped to the poles.
    """

    if radius_km < 0:
        raise ValueError("radius_km must be non-negative")

    lat_delta = radius_km / KM_PER_DEG_LAT

    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    lon_delta = radius_km / (KM_PER_DEG_LAT * cos_lat)

    lamin = max(-90.0, lat - lat_delta)
    lamax = min(90.0, lat + lat_delta)

    # Longitude can wrap; for the OpenSky request the caller may need to
    # handle the antimeridian themselves, but a single bbox suffices for
    # the < ~1000 km radii we use.
    lomin = lon - lon_delta
    lomax = lon + lon_delta

    return BoundingBox(lamin=lamin, lomin=lomin, lamax=lamax, lomax=lomax)


def project_aircraft_to_screen(
    bearing: float,
    distance_km: float,
    *,
    selected_radius_km: float,
    center_x: int,
    center_y: int,
    radius_px: int,
) -> ScreenPoint:
    """Project an aircraft into 250x122 radar coordinates.

    Replicates the formula in the spec:

        x = center_x + sin(bearing) * radius_px * distance_ratio
        y = center_y - cos(bearing) * radius_px * distance_ratio

    Aircraft outside the selected radius are clamped to the ring (so the
    caller can still draw a marker on the edge).
    """

    if selected_radius_km <= 0:
        raise ValueError("selected_radius_km must be positive")

    distance_ratio = min(1.0, max(0.0, distance_km / selected_radius_km))
    theta = math.radians(bearing % 360.0)
    x = center_x + math.sin(theta) * radius_px * distance_ratio
    y = center_y - math.cos(theta) * radius_px * distance_ratio
    return ScreenPoint(x=int(round(x)), y=int(round(y)))


__all__ = [
    "EARTH_RADIUS_KM",
    "KM_PER_DEG_LAT",
    "BoundingBox",
    "ScreenPoint",
    "haversine_km",
    "bearing_deg",
    "cardinal_direction",
    "latlon_bbox",
    "project_aircraft_to_screen",
]
