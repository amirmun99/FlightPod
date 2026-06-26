"""Aircraft pipeline: filter, enrich (distance/bearing/age), sort.

Inputs come from :mod:`flightpaper.opensky`; outputs feed the renderer and
the ``/api/secure/aircraft`` endpoint.
"""

from .filters import FilterConfig, filter_aircraft
from .processor import UserPosition, enrich_aircraft, process_states
from .sort import sort_by_distance, sort_overhead_first

__all__ = [
    "FilterConfig",
    "UserPosition",
    "enrich_aircraft",
    "filter_aircraft",
    "process_states",
    "sort_by_distance",
    "sort_overhead_first",
]
