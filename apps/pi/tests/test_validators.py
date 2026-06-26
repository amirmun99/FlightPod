"""Tests for flightpaper.utils.validators."""

from __future__ import annotations

from flightpaper.utils.validators import (
    is_reasonable_accuracy,
    is_reasonable_altitude_m,
    is_reasonable_timestamp,
    is_reasonable_track_deg,
    is_reasonable_velocity_mps,
    is_valid_lat,
    is_valid_lon,
)


def test_lat_range() -> None:
    assert is_valid_lat(0.0) is True
    assert is_valid_lat(90.0) is True
    assert is_valid_lat(-90.0) is True
    assert is_valid_lat(43.3255) is True
    assert is_valid_lat(90.0001) is False
    assert is_valid_lat(-90.0001) is False
    assert is_valid_lat(None) is False
    assert is_valid_lat("43.3") is False


def test_lon_range() -> None:
    assert is_valid_lon(0.0) is True
    assert is_valid_lon(180.0) is True
    assert is_valid_lon(-180.0) is True
    assert is_valid_lon(180.0001) is False
    assert is_valid_lon(-180.0001) is False


def test_accuracy() -> None:
    assert is_reasonable_accuracy(None) is True
    assert is_reasonable_accuracy(0.0) is True
    assert is_reasonable_accuracy(8.5) is True
    assert is_reasonable_accuracy(9_999.0) is True
    assert is_reasonable_accuracy(10_001.0) is False
    assert is_reasonable_accuracy(-1.0) is False


def test_timestamp_window() -> None:
    now = 1_700_000_000
    assert is_reasonable_timestamp(now, now=now) is True
    assert is_reasonable_timestamp(now - 60, now=now) is True
    assert is_reasonable_timestamp(now + 60, now=now) is True
    assert is_reasonable_timestamp(now - 25 * 3600, now=now) is False
    assert is_reasonable_timestamp(now + 10 * 60, now=now) is False
    assert is_reasonable_timestamp(None, now=now) is False
    assert is_reasonable_timestamp("not-a-time", now=now) is False  # type: ignore[arg-type]


def test_altitude_velocity_track() -> None:
    assert is_reasonable_altitude_m(None) is True
    assert is_reasonable_altitude_m(0.0) is True
    assert is_reasonable_altitude_m(12_500.0) is True
    assert is_reasonable_altitude_m(50_000.0) is False
    assert is_reasonable_altitude_m(-1_000.0) is False

    assert is_reasonable_velocity_mps(None) is True
    assert is_reasonable_velocity_mps(0.0) is True
    assert is_reasonable_velocity_mps(250.0) is True
    assert is_reasonable_velocity_mps(800.0) is False
    assert is_reasonable_velocity_mps(-1.0) is False

    assert is_reasonable_track_deg(None) is True
    assert is_reasonable_track_deg(0.0) is True
    assert is_reasonable_track_deg(359.9) is True
    assert is_reasonable_track_deg(360.0) is False
    assert is_reasonable_track_deg(-1.0) is False
