"""Enrich raw aircraft with distance, bearing, and age relative to the user.

This is the single chokepoint where the user's GPS first meets the OpenSky
states. Downstream code (renderer, sort, API) reads the derived fields and
never re-computes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..opensky.models import Aircraft, OpenSkyStates
from ..utils.geo import bearing_deg, haversine_km
from .filters import FilterConfig, filter_aircraft
from .sort import sort_by_distance, sort_overhead_first


@dataclass(frozen=True)
class UserPosition:
    """Minimal shape used by the aircraft pipeline.

    The full :class:`flightpaper.location.models.Location` (Phase 3) is a
    superset; this struct keeps the pipeline decoupled from the location
    manager.
    """

    lat: float
    lon: float


def enrich_aircraft(
    aircraft: Iterable[Aircraft],
    *,
    user: UserPosition,
    now_ts: int,
) -> list[Aircraft]:
    """Compute and assign ``distance_km``, ``bearing_deg``, ``age_seconds``.

    Returns a new list with the same ``Aircraft`` instances mutated in
    place. Aircraft with missing lat/lon are skipped (use the filter step
    upstream to drop them earlier).
    """

    out: list[Aircraft] = []
    for ac in aircraft:
        if ac.latitude is None or ac.longitude is None:
            continue
        ac.distance_km = haversine_km(user.lat, user.lon, ac.latitude, ac.longitude)
        ac.bearing_deg = bearing_deg(user.lat, user.lon, ac.latitude, ac.longitude)
        ts = ac.time_position if ac.time_position is not None else ac.last_contact
        ac.age_seconds = max(0, now_ts - ts) if ts is not None else None
        out.append(ac)
    return out


def process_states(
    states: OpenSkyStates,
    *,
    user: UserPosition,
    config: FilterConfig,
    now_ts: int,
    sort: str = "distance",
) -> list[Aircraft]:
    """Full pipeline: filter → enrich → radius cut-off → sort.

    Parameters
    ----------
    states: parsed OpenSky response.
    user: current user position.
    config: filter knobs (ground inclusion, max age, optional radius cutoff).
    now_ts: current unix seconds; used for age and freshness.
    sort: ``"distance"`` (default) or ``"overhead"``.
    """

    visible = filter_aircraft(states.aircraft, config=config, now_ts=now_ts)
    enriched = enrich_aircraft(visible, user=user, now_ts=now_ts)

    if config.radius_km is not None:
        enriched = [
            ac
            for ac in enriched
            if ac.distance_km is not None and ac.distance_km <= config.radius_km
        ]

    if sort == "overhead":
        # Overhead threshold is encoded in the renderer/UI config; for the
        # pipeline we use 2 km as the spec default. Callers wanting a
        # different threshold should sort the result themselves.
        return sort_overhead_first(enriched, overhead_threshold_km=2.0)
    return sort_by_distance(enriched)


__all__ = ["UserPosition", "enrich_aircraft", "process_states"]
