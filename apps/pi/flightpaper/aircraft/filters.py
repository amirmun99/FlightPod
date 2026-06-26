"""Filter rules for raw OpenSky aircraft (spec §14)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..opensky.models import Aircraft
from ..utils.validators import is_valid_lat, is_valid_lon


@dataclass(frozen=True)
class FilterConfig:
    include_ground_aircraft: bool = False
    max_age_seconds: int = 120
    radius_km: float | None = None  # Hard cutoff after distance is computed.


def _too_old(ac: Aircraft, *, now_ts: int, max_age_s: int) -> bool:
    # Prefer time_position; fall back to last_contact.
    ts = ac.time_position if ac.time_position is not None else ac.last_contact
    if ts is None:
        # No timestamp at all — treat as stale.
        return True
    return (now_ts - ts) > max_age_s


def filter_aircraft(
    aircraft: Iterable[Aircraft],
    *,
    config: FilterConfig,
    now_ts: int,
) -> list[Aircraft]:
    """Drop aircraft that fail basic visibility rules.

    The ``radius_km`` cutoff is *not* applied here — that's the processor's
    job (it requires the user position). This function handles rules that
    only need the aircraft state.
    """

    out: list[Aircraft] = []
    for ac in aircraft:
        if not is_valid_lat(ac.latitude) or not is_valid_lon(ac.longitude):
            continue
        if ac.on_ground and not config.include_ground_aircraft:
            continue
        if _too_old(ac, now_ts=now_ts, max_age_s=config.max_age_seconds):
            continue
        out.append(ac)
    return out


__all__ = ["FilterConfig", "filter_aircraft"]
