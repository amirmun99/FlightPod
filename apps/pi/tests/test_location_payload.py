"""Tests for flightpaper.location.payload.validate_location_payload."""

from __future__ import annotations

import pytest

from flightpaper.location.payload import (
    InvalidLocationPayload,
    validate_location_payload,
)


NOW = 1_700_000_000


def _good_payload(**overrides) -> dict:
    base = {
        "lat": 43.3255,
        "lon": -79.7990,
        "accuracy_m": 8.5,
        "altitude_m": 120.0,
        "heading_deg": 52.0,
        "speed_mps": 1.4,
        "timestamp": NOW,
        "source": "iphone_background",
    }
    base.update(overrides)
    return base


def test_accepts_canonical_payload() -> None:
    payload = validate_location_payload(_good_payload(), now=NOW)
    assert payload.lat == 43.3255
    assert payload.lon == -79.7990
    assert payload.accuracy_m == 8.5
    assert payload.source == "iphone_background"
    assert payload.timestamp == NOW


def test_optional_fields_may_be_missing() -> None:
    payload = validate_location_payload(
        {
            "lat": 0.0,
            "lon": 0.0,
            "timestamp": NOW,
            "source": "iphone_foreground",
        },
        now=NOW,
    )
    assert payload.accuracy_m is None
    assert payload.altitude_m is None
    assert payload.heading_deg is None
    assert payload.speed_mps is None


def test_rejects_non_mapping() -> None:
    with pytest.raises(InvalidLocationPayload):
        validate_location_payload([1, 2, 3], now=NOW)  # type: ignore[arg-type]


def test_rejects_missing_required_field() -> None:
    payload = _good_payload()
    del payload["lat"]
    with pytest.raises(InvalidLocationPayload, match="missing field: lat"):
        validate_location_payload(payload, now=NOW)


def test_rejects_out_of_range_lat() -> None:
    with pytest.raises(InvalidLocationPayload, match="lat"):
        validate_location_payload(_good_payload(lat=95.0), now=NOW)


def test_rejects_out_of_range_lon() -> None:
    with pytest.raises(InvalidLocationPayload, match="lon"):
        validate_location_payload(_good_payload(lon=-200.0), now=NOW)


def test_rejects_non_numeric_lat() -> None:
    with pytest.raises(InvalidLocationPayload):
        validate_location_payload(_good_payload(lat="north"), now=NOW)


def test_rejects_future_timestamp() -> None:
    with pytest.raises(InvalidLocationPayload, match="timestamp"):
        validate_location_payload(_good_payload(timestamp=NOW + 10 * 60), now=NOW)


def test_accepts_recent_past_timestamp() -> None:
    payload = validate_location_payload(_good_payload(timestamp=NOW - 30), now=NOW)
    assert payload.timestamp == NOW - 30


def test_rejects_distant_past_timestamp() -> None:
    with pytest.raises(InvalidLocationPayload, match="timestamp"):
        validate_location_payload(_good_payload(timestamp=NOW - 25 * 3600), now=NOW)


def test_rejects_unsupported_source() -> None:
    with pytest.raises(InvalidLocationPayload, match="source"):
        validate_location_payload(_good_payload(source="android_background"), now=NOW)


def test_rejects_negative_accuracy() -> None:
    with pytest.raises(InvalidLocationPayload, match="accuracy"):
        validate_location_payload(_good_payload(accuracy_m=-1.0), now=NOW)


def test_rejects_huge_accuracy() -> None:
    with pytest.raises(InvalidLocationPayload, match="accuracy"):
        validate_location_payload(_good_payload(accuracy_m=100_000.0), now=NOW)


def test_rejects_impossible_altitude() -> None:
    with pytest.raises(InvalidLocationPayload, match="altitude"):
        validate_location_payload(_good_payload(altitude_m=50_000.0), now=NOW)


def test_rejects_impossible_velocity() -> None:
    with pytest.raises(InvalidLocationPayload, match="speed"):
        validate_location_payload(_good_payload(speed_mps=1000.0), now=NOW)


def test_rejects_invalid_heading() -> None:
    with pytest.raises(InvalidLocationPayload, match="heading"):
        validate_location_payload(_good_payload(heading_deg=361.0), now=NOW)
