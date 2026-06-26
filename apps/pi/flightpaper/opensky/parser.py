"""Parse OpenSky ``/states/all`` JSON into :class:`Aircraft` instances."""

from __future__ import annotations

import logging
from typing import Any

from .models import Aircraft, OpenSkyStates, state_vector_field

log = logging.getLogger(__name__)


def _maybe_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _maybe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _maybe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _maybe_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.lower() in {"true", "1", "yes"}
    return None


def parse_state_vector(row: list[Any]) -> Aircraft | None:
    """Convert one OpenSky state-vector row into an :class:`Aircraft`.

    Returns ``None`` when the row is too short to identify the aircraft
    (no ``icao24``).
    """

    icao24 = _maybe_str(state_vector_field(row, "icao24"))
    if not icao24:
        return None

    return Aircraft(
        icao24=icao24.lower(),
        callsign=_maybe_str(state_vector_field(row, "callsign")),
        origin_country=_maybe_str(state_vector_field(row, "origin_country")),
        time_position=_maybe_int(state_vector_field(row, "time_position")),
        last_contact=_maybe_int(state_vector_field(row, "last_contact")),
        longitude=_maybe_float(state_vector_field(row, "longitude")),
        latitude=_maybe_float(state_vector_field(row, "latitude")),
        baro_altitude_m=_maybe_float(state_vector_field(row, "baro_altitude_m")),
        on_ground=bool(_maybe_bool(state_vector_field(row, "on_ground")) or False),
        velocity_mps=_maybe_float(state_vector_field(row, "velocity_mps")),
        true_track_deg=_maybe_float(state_vector_field(row, "true_track_deg")),
        vertical_rate_mps=_maybe_float(state_vector_field(row, "vertical_rate_mps")),
        geo_altitude_m=_maybe_float(state_vector_field(row, "geo_altitude_m")),
        squawk=_maybe_str(state_vector_field(row, "squawk")),
        spi=_maybe_bool(state_vector_field(row, "spi")),
        position_source=_maybe_int(state_vector_field(row, "position_source")),
        category=_maybe_int(state_vector_field(row, "category")),
    )


def parse_states_response(payload: dict[str, Any]) -> OpenSkyStates:
    """Parse the JSON returned by ``/states/all``.

    The OpenSky payload uses ``{"time": <unix>, "states": [[...], ...]}``.
    When ``states`` is ``null`` (no aircraft in the bbox), we still return a
    valid empty :class:`OpenSkyStates`.
    """

    raw_time = payload.get("time", 0)
    try:
        ts = int(raw_time)
    except (TypeError, ValueError):
        ts = 0

    raw_states = payload.get("states") or []
    aircraft: list[Aircraft] = []

    for row in raw_states:
        if not isinstance(row, list):
            continue
        ac = parse_state_vector(row)
        if ac is not None:
            aircraft.append(ac)
        else:
            log.debug("skipping unparseable state vector row")

    return OpenSkyStates(time=ts, aircraft=aircraft)


__all__ = ["parse_state_vector", "parse_states_response"]
