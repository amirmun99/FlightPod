"""Sort orderings for enriched aircraft."""

from __future__ import annotations

from typing import Iterable

from ..opensky.models import Aircraft

# A "very large" sentinel for sorting aircraft whose distance is unknown:
# they trail behind all known-distance entries deterministically.
_INF = float("inf")


def sort_by_distance(aircraft: Iterable[Aircraft]) -> list[Aircraft]:
    """Closest first; unknown distance trails."""

    return sorted(
        aircraft,
        key=lambda ac: (
            ac.distance_km if ac.distance_km is not None else _INF,
            ac.icao24,
        ),
    )


def sort_overhead_first(
    aircraft: Iterable[Aircraft],
    *,
    overhead_threshold_km: float,
) -> list[Aircraft]:
    """Aircraft within ``overhead_threshold_km`` first (closest first inside
    that group), then everything else closest first.
    """

    items = list(aircraft)

    def key(ac: Aircraft) -> tuple[int, float, str]:
        d = ac.distance_km if ac.distance_km is not None else _INF
        overhead_rank = 0 if d <= overhead_threshold_km else 1
        return (overhead_rank, d, ac.icao24)

    return sorted(items, key=key)


__all__ = ["sort_by_distance", "sort_overhead_first"]
