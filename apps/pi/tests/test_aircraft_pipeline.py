"""Tests for the aircraft filter / processor / sort pipeline."""

from __future__ import annotations

from flightpaper.aircraft.filters import FilterConfig, filter_aircraft
from flightpaper.aircraft.processor import UserPosition, enrich_aircraft, process_states
from flightpaper.aircraft.sort import sort_by_distance, sort_overhead_first
from flightpaper.opensky.models import Aircraft, OpenSkyStates


NOW = 1_700_000_000
USER = UserPosition(lat=43.3255, lon=-79.7990)


def _ac(
    icao: str,
    *,
    lat: float | None = 43.33,
    lon: float | None = -79.80,
    on_ground: bool = False,
    last_contact: int | None = NOW - 5,
    time_position: int | None = NOW - 5,
    callsign: str | None = "ABC123",
) -> Aircraft:
    return Aircraft(
        icao24=icao,
        callsign=callsign,
        origin_country="Canada",
        time_position=time_position,
        last_contact=last_contact,
        longitude=lon,
        latitude=lat,
        baro_altitude_m=9000.0,
        on_ground=on_ground,
        velocity_mps=240.0,
        true_track_deg=82.0,
        vertical_rate_mps=0.0,
        geo_altitude_m=9050.0,
    )


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_drops_missing_position(self) -> None:
        aircraft = [_ac("a"), _ac("b", lat=None), _ac("c", lon=None)]
        result = filter_aircraft(aircraft, config=FilterConfig(), now_ts=NOW)
        assert [ac.icao24 for ac in result] == ["a"]

    def test_drops_ground_by_default(self) -> None:
        aircraft = [_ac("a"), _ac("b", on_ground=True)]
        result = filter_aircraft(aircraft, config=FilterConfig(), now_ts=NOW)
        assert [ac.icao24 for ac in result] == ["a"]

    def test_keeps_ground_when_configured(self) -> None:
        aircraft = [_ac("a"), _ac("b", on_ground=True)]
        result = filter_aircraft(
            aircraft, config=FilterConfig(include_ground_aircraft=True), now_ts=NOW
        )
        assert {ac.icao24 for ac in result} == {"a", "b"}

    def test_drops_too_old(self) -> None:
        aircraft = [
            _ac("a", time_position=NOW - 30),
            _ac("b", time_position=NOW - 300),  # stale
        ]
        result = filter_aircraft(aircraft, config=FilterConfig(max_age_seconds=120), now_ts=NOW)
        assert [ac.icao24 for ac in result] == ["a"]

    def test_falls_back_to_last_contact_for_age(self) -> None:
        aircraft = [_ac("a", time_position=None, last_contact=NOW - 30)]
        result = filter_aircraft(aircraft, config=FilterConfig(max_age_seconds=120), now_ts=NOW)
        assert [ac.icao24 for ac in result] == ["a"]

    def test_drops_with_no_timestamp(self) -> None:
        aircraft = [_ac("a", time_position=None, last_contact=None)]
        result = filter_aircraft(aircraft, config=FilterConfig(), now_ts=NOW)
        assert result == []


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


class TestEnrich:
    def test_assigns_distance_and_bearing(self) -> None:
        ac = _ac("a", lat=43.33, lon=-79.80, time_position=NOW - 8)
        enriched = enrich_aircraft([ac], user=USER, now_ts=NOW)
        assert len(enriched) == 1
        e = enriched[0]
        assert e.distance_km is not None and 0 < e.distance_km < 2  # very close
        assert e.bearing_deg is not None and 0 <= e.bearing_deg < 360
        assert e.age_seconds == 8

    def test_skips_missing_position(self) -> None:
        enriched = enrich_aircraft(
            [_ac("a"), _ac("b", lat=None)],
            user=USER,
            now_ts=NOW,
        )
        assert [ac.icao24 for ac in enriched] == ["a"]

    def test_handles_missing_timestamp(self) -> None:
        ac = _ac("a", time_position=None, last_contact=None)
        enriched = enrich_aircraft([ac], user=USER, now_ts=NOW)
        assert enriched[0].age_seconds is None


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


def _with_distance(icao: str, d: float | None) -> Aircraft:
    ac = _ac(icao)
    ac.distance_km = d
    return ac


class TestSort:
    def test_sort_by_distance_unknown_trails(self) -> None:
        result = sort_by_distance(
            [
                _with_distance("c", 10),
                _with_distance("a", 1),
                _with_distance("z", None),
                _with_distance("b", 5),
            ]
        )
        assert [ac.icao24 for ac in result] == ["a", "b", "c", "z"]

    def test_overhead_first(self) -> None:
        result = sort_overhead_first(
            [
                _with_distance("c", 10),
                _with_distance("a", 1.5),   # overhead (≤ 2)
                _with_distance("b", 0.5),   # overhead, closer
                _with_distance("d", 3),     # not overhead
            ],
            overhead_threshold_km=2.0,
        )
        assert [ac.icao24 for ac in result] == ["b", "a", "d", "c"]


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


class TestProcessStates:
    def test_filters_and_radius_cutoff(self) -> None:
        states = OpenSkyStates(
            time=NOW,
            aircraft=[
                _ac("near", lat=43.33, lon=-79.80),
                _ac("far", lat=44.0, lon=-79.0),       # > 100 km
                _ac("ground", on_ground=True),
                _ac("stale", time_position=NOW - 300),
                _ac("no_pos", lat=None, lon=None),
            ],
        )
        result = process_states(
            states,
            user=USER,
            config=FilterConfig(radius_km=25.0, max_age_seconds=120),
            now_ts=NOW,
        )
        assert [ac.icao24 for ac in result] == ["near"]

    def test_sort_overhead(self) -> None:
        # Two aircraft within the bbox, one overhead, one further.
        states = OpenSkyStates(
            time=NOW,
            aircraft=[
                _ac("far_one", lat=43.45, lon=-79.95),
                _ac("overhead", lat=43.3260, lon=-79.7995),
            ],
        )
        result = process_states(
            states,
            user=USER,
            config=FilterConfig(radius_km=50.0),
            now_ts=NOW,
            sort="overhead",
        )
        assert result[0].icao24 == "overhead"
