"""Tests for flightpaper.opensky.parser."""

from __future__ import annotations

from flightpaper.opensky.parser import parse_state_vector, parse_states_response


def _row(**overrides: object) -> list[object]:
    """Build a canonical 17-element OpenSky state vector with sensible defaults."""

    row = [
        "AbCdEf",        # icao24 (will be lowercased)
        "ACA123  ",      # callsign with whitespace padding
        "Canada",        # origin_country
        1_700_000_000,   # time_position
        1_700_000_010,   # last_contact
        -79.81,          # longitude
        43.33,           # latitude
        9525.0,          # baro_altitude_m
        False,           # on_ground
        240.0,           # velocity_mps
        82.0,            # true_track_deg
        0.5,             # vertical_rate_mps
        None,            # sensors
        9540.0,          # geo_altitude_m
        "1234",          # squawk
        False,           # spi
        0,               # position_source
    ]
    for k, v in overrides.items():
        idx = {
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
            "geo_altitude_m": 13,
            "squawk": 14,
            "spi": 15,
            "position_source": 16,
        }[k]
        row[idx] = v
    return row


def test_canonical_row_parses() -> None:
    ac = parse_state_vector(_row())
    assert ac is not None
    assert ac.icao24 == "abcdef"
    assert ac.callsign == "ACA123"  # whitespace stripped
    assert ac.origin_country == "Canada"
    assert ac.longitude == -79.81
    assert ac.latitude == 43.33
    assert ac.baro_altitude_m == 9525.0
    assert ac.on_ground is False
    assert ac.velocity_mps == 240.0
    assert ac.true_track_deg == 82.0
    assert ac.vertical_rate_mps == 0.5
    assert ac.geo_altitude_m == 9540.0
    assert ac.squawk == "1234"


def test_extended_row_with_category() -> None:
    row = _row()
    row.append(3)  # category
    ac = parse_state_vector(row)
    assert ac is not None
    assert ac.category == 3


def test_short_row_missing_trailing_fields() -> None:
    # OpenSky rarely returns short rows but we tolerate them.
    short = _row()[:10]
    ac = parse_state_vector(short)
    assert ac is not None
    assert ac.icao24 == "abcdef"
    assert ac.geo_altitude_m is None
    assert ac.squawk is None


def test_missing_icao24_returns_none() -> None:
    row = _row(icao24="")
    assert parse_state_vector(row) is None

    row = _row(icao24=None)
    assert parse_state_vector(row) is None


def test_empty_callsign_becomes_none() -> None:
    ac = parse_state_vector(_row(callsign="        "))
    assert ac is not None
    assert ac.callsign is None

    ac = parse_state_vector(_row(callsign=""))
    assert ac is not None
    assert ac.callsign is None


def test_null_position_preserved() -> None:
    ac = parse_state_vector(_row(latitude=None, longitude=None))
    assert ac is not None
    assert ac.latitude is None
    assert ac.longitude is None


def test_string_floats_coerced() -> None:
    # OpenSky returns numeric JSON, but be forgiving.
    ac = parse_state_vector(_row(longitude="-79.81", latitude="43.33"))
    assert ac is not None
    assert ac.longitude == -79.81
    assert ac.latitude == 43.33


def test_on_ground_truthy_values() -> None:
    assert parse_state_vector(_row(on_ground=True)).on_ground is True  # type: ignore[union-attr]
    assert parse_state_vector(_row(on_ground=1)).on_ground is True  # type: ignore[union-attr]
    assert parse_state_vector(_row(on_ground="true")).on_ground is True  # type: ignore[union-attr]
    assert parse_state_vector(_row(on_ground=False)).on_ground is False  # type: ignore[union-attr]
    assert parse_state_vector(_row(on_ground=None)).on_ground is False  # type: ignore[union-attr]


def test_parse_states_response_empty_states() -> None:
    payload = {"time": 1_700_000_000, "states": None}
    result = parse_states_response(payload)
    assert result.time == 1_700_000_000
    assert result.count == 0


def test_parse_states_response_skips_non_list_rows() -> None:
    payload = {
        "time": 1_700_000_000,
        "states": [_row(), "not-a-row", None, _row(icao24="ff00aa")],
    }
    result = parse_states_response(payload)
    assert result.count == 2
    assert {ac.icao24 for ac in result.aircraft} == {"abcdef", "ff00aa"}


def test_parse_states_response_skips_unparseable_rows() -> None:
    # A row with no icao24 should be skipped, not crash.
    payload = {"time": 1_700_000_000, "states": [_row(icao24=None), _row()]}
    result = parse_states_response(payload)
    assert result.count == 1


def test_parse_states_response_bad_time_defaults_to_zero() -> None:
    payload = {"time": "not-a-time", "states": []}
    result = parse_states_response(payload)
    assert result.time == 0
