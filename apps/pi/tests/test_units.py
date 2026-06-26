"""Tests for flightpaper.utils.units."""

from __future__ import annotations

import pytest

from flightpaper.utils.units import (
    feet_to_meters,
    km_to_nm,
    knots_to_mps,
    meters_to_feet,
    mps_to_fpm,
    mps_to_kmh,
    mps_to_knots,
    nm_to_km,
)


def test_meters_to_feet_known() -> None:
    # 1 m = 3.28084 ft
    assert meters_to_feet(1.0) == pytest.approx(3.28084, rel=1e-4)
    # FL310 = 31,000 ft = ~9,448.8 m
    assert meters_to_feet(9448.8) == pytest.approx(31000.0, rel=1e-3)


def test_feet_to_meters_round_trip() -> None:
    for v in (0.0, 100.0, 31250.0, 100000.0):
        assert feet_to_meters(meters_to_feet(v)) == pytest.approx(v, rel=1e-6)


def test_mps_to_knots_known() -> None:
    # 1 m/s = 1.94384 kt
    assert mps_to_knots(1.0) == pytest.approx(1.94384, rel=1e-4)
    # 100 m/s ≈ 194.38 kt
    assert mps_to_knots(100.0) == pytest.approx(194.384, rel=1e-4)


def test_knots_to_mps_round_trip() -> None:
    for v in (0.0, 1.0, 250.0, 600.0):
        assert knots_to_mps(mps_to_knots(v)) == pytest.approx(v, rel=1e-6)


def test_km_to_nm_known() -> None:
    # 1.852 km = 1 nm
    assert km_to_nm(1.852) == pytest.approx(1.0, rel=1e-6)
    assert km_to_nm(25.0) == pytest.approx(13.4989, rel=1e-3)


def test_nm_to_km_round_trip() -> None:
    for v in (0.0, 1.0, 25.0, 100.0):
        assert nm_to_km(km_to_nm(v)) == pytest.approx(v, rel=1e-6)


def test_mps_to_fpm_known() -> None:
    # 1 m/s = 196.85 ft/min
    assert mps_to_fpm(1.0) == pytest.approx(196.85, rel=1e-3)
    # Typical climb 10 m/s ≈ 1968 ft/min
    assert mps_to_fpm(10.0) == pytest.approx(1968.5, rel=1e-3)


def test_mps_to_kmh_known() -> None:
    assert mps_to_kmh(1.0) == pytest.approx(3.6)
    assert mps_to_kmh(10.0) == pytest.approx(36.0)


def test_none_passes_through() -> None:
    assert meters_to_feet(None) is None
    assert mps_to_knots(None) is None
    assert km_to_nm(None) is None
    assert mps_to_fpm(None) is None
    assert mps_to_kmh(None) is None
    assert knots_to_mps(None) is None
    assert feet_to_meters(None) is None
    assert nm_to_km(None) is None
