"""Tests for flightpaper.utils.geo."""

from __future__ import annotations

import math

import pytest

from flightpaper.utils.geo import (
    bearing_deg,
    cardinal_direction,
    haversine_km,
    latlon_bbox,
    project_aircraft_to_screen,
)


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------


class TestHaversine:
    def test_same_point_is_zero(self) -> None:
        assert haversine_km(43.3, -79.8, 43.3, -79.8) == pytest.approx(0.0, abs=1e-9)

    def test_antipodes_are_half_circumference(self) -> None:
        # Within 0.1% of pi * R (great-circle half-perimeter).
        d = haversine_km(0.0, 0.0, 0.0, 180.0)
        expected = math.pi * 6371.0088
        assert d == pytest.approx(expected, rel=1e-3)

    def test_toronto_to_hamilton(self) -> None:
        # Pearson Intl (43.677, -79.631) to Hamilton (43.255, -79.872).
        d = haversine_km(43.6777, -79.6306, 43.2557, -79.8711)
        # Reference: ~52 km.
        assert 49.0 < d < 56.0

    def test_one_degree_lat_is_about_111km(self) -> None:
        d = haversine_km(0.0, 0.0, 1.0, 0.0)
        assert 110.5 < d < 111.5

    def test_one_degree_lon_at_equator_is_about_111km(self) -> None:
        d = haversine_km(0.0, 0.0, 0.0, 1.0)
        assert 110.5 < d < 111.5

    def test_lon_compresses_at_higher_lat(self) -> None:
        # At 60° latitude, 1° of longitude is ~half of equator value.
        d_equator = haversine_km(0.0, 0.0, 0.0, 1.0)
        d_north = haversine_km(60.0, 0.0, 60.0, 1.0)
        assert d_north < d_equator
        assert d_north == pytest.approx(d_equator * 0.5, rel=0.05)

    def test_pole_to_pole(self) -> None:
        d = haversine_km(90.0, 0.0, -90.0, 0.0)
        assert d == pytest.approx(math.pi * 6371.0088, rel=1e-3)


# ---------------------------------------------------------------------------
# Bearing
# ---------------------------------------------------------------------------


class TestBearing:
    def test_north_is_zero(self) -> None:
        assert bearing_deg(0.0, 0.0, 1.0, 0.0) == pytest.approx(0.0, abs=1e-6)

    def test_east_is_ninety(self) -> None:
        assert bearing_deg(0.0, 0.0, 0.0, 1.0) == pytest.approx(90.0, abs=1e-6)

    def test_south_is_one_eighty(self) -> None:
        assert bearing_deg(0.0, 0.0, -1.0, 0.0) == pytest.approx(180.0, abs=1e-6)

    def test_west_is_two_seventy(self) -> None:
        assert bearing_deg(0.0, 0.0, 0.0, -1.0) == pytest.approx(270.0, abs=1e-6)

    def test_northeast_quadrant(self) -> None:
        b = bearing_deg(0.0, 0.0, 1.0, 1.0)
        assert 0.0 < b < 90.0

    def test_range_is_zero_to_360(self) -> None:
        for lat2, lon2 in [(1, 1), (-1, 1), (-1, -1), (1, -1)]:
            b = bearing_deg(0.0, 0.0, float(lat2), float(lon2))
            assert 0.0 <= b < 360.0


# ---------------------------------------------------------------------------
# Cardinal direction
# ---------------------------------------------------------------------------


class TestCardinalDirection:
    @pytest.mark.parametrize(
        "deg,expected",
        [
            (0.0, "N"),
            (22.4, "N"),
            (22.6, "NE"),
            (45.0, "NE"),
            (67.5, "E"),
            (90.0, "E"),
            (135.0, "SE"),
            (180.0, "S"),
            (225.0, "SW"),
            (270.0, "W"),
            (315.0, "NW"),
            (337.4, "NW"),
            (337.6, "N"),
            (359.9, "N"),
        ],
    )
    def test_known_boundaries(self, deg: float, expected: str) -> None:
        assert cardinal_direction(deg) == expected

    def test_wraps_above_360(self) -> None:
        assert cardinal_direction(720.0) == "N"
        assert cardinal_direction(810.0) == "E"

    def test_handles_negative(self) -> None:
        assert cardinal_direction(-1.0) == "N"
        assert cardinal_direction(-90.0) == "W"


# ---------------------------------------------------------------------------
# Bounding box
# ---------------------------------------------------------------------------


class TestBoundingBox:
    def test_radius_zero_is_point(self) -> None:
        bb = latlon_bbox(43.0, -79.0, 0.0)
        assert bb.lamin == bb.lamax == 43.0
        assert bb.lomin == bb.lomax == -79.0

    def test_radius_25km_at_43_lat(self) -> None:
        bb = latlon_bbox(43.0, -79.0, 25.0)
        # Latitude span ≈ 25 / 111 ≈ 0.225°.
        assert bb.lamin == pytest.approx(43.0 - 0.225, abs=0.01)
        assert bb.lamax == pytest.approx(43.0 + 0.225, abs=0.01)
        # Longitude span is larger because cos(43°) ≈ 0.73.
        lon_span = (bb.lomax - bb.lomin) / 2
        assert lon_span == pytest.approx(0.225 / math.cos(math.radians(43.0)), rel=0.01)

    def test_pole_does_not_explode(self) -> None:
        bb = latlon_bbox(89.9, 0.0, 50.0)
        # Lon span is huge near the pole; just confirm it computes finite.
        assert math.isfinite(bb.lomin)
        assert math.isfinite(bb.lomax)

    def test_negative_radius_raises(self) -> None:
        with pytest.raises(ValueError):
            latlon_bbox(0.0, 0.0, -1.0)

    def test_bbox_clamps_to_pole(self) -> None:
        bb = latlon_bbox(89.5, 0.0, 200.0)
        assert bb.lamax <= 90.0


# ---------------------------------------------------------------------------
# Radar projection
# ---------------------------------------------------------------------------


class TestProjection:
    def test_zero_distance_is_center(self) -> None:
        p = project_aircraft_to_screen(
            bearing=0.0,
            distance_km=0.0,
            selected_radius_km=25.0,
            center_x=100,
            center_y=50,
            radius_px=40,
        )
        assert (p.x, p.y) == (100, 50)

    def test_north_at_full_radius_is_above(self) -> None:
        # Bearing 0 => north; screen y axis is inverted so y decreases.
        p = project_aircraft_to_screen(
            bearing=0.0,
            distance_km=25.0,
            selected_radius_km=25.0,
            center_x=100,
            center_y=50,
            radius_px=40,
        )
        assert p.x == 100
        assert p.y == 10

    def test_east_at_full_radius_is_right(self) -> None:
        p = project_aircraft_to_screen(
            bearing=90.0,
            distance_km=25.0,
            selected_radius_km=25.0,
            center_x=100,
            center_y=50,
            radius_px=40,
        )
        assert p.x == 140
        assert p.y == 50

    def test_outside_radius_clamps_to_ring(self) -> None:
        p_in = project_aircraft_to_screen(
            bearing=45.0,
            distance_km=25.0,
            selected_radius_km=25.0,
            center_x=100,
            center_y=50,
            radius_px=40,
        )
        p_out = project_aircraft_to_screen(
            bearing=45.0,
            distance_km=100.0,
            selected_radius_km=25.0,
            center_x=100,
            center_y=50,
            radius_px=40,
        )
        assert (p_in.x, p_in.y) == (p_out.x, p_out.y)

    def test_zero_radius_raises(self) -> None:
        with pytest.raises(ValueError):
            project_aircraft_to_screen(
                bearing=0.0,
                distance_km=1.0,
                selected_radius_km=0.0,
                center_x=0,
                center_y=0,
                radius_px=1,
            )
