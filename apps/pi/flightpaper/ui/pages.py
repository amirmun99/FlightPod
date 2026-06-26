"""Page identifiers and the cycle order used by the next/prev buttons.

The full set of pages the renderer knows about lives in
:data:`flightpaper.display.renderer._PAGES`. This module only enumerates
the ones reachable from button input — special pages like ``boot``,
``pairing``, and ``shutdown_confirm`` are not in the cycle.
"""

from __future__ import annotations


# Pages reachable by short button press (next/prev). Order matches the spec §18
# preference: radar is the default after pairing, followed by closest, list,
# and status.
CYCLE_PAGES: tuple[str, ...] = ("radar", "closest", "list", "status")

# All renderable pages.
PAGES: tuple[str, ...] = (
    "boot",
    "pairing",
    "radar",
    "closest",
    "list",
    "status",
    "shutdown_confirm",
)


def next_page(current: str) -> str:
    """Page after ``current`` in the cycle; wraps around."""

    if current not in CYCLE_PAGES:
        return CYCLE_PAGES[0]
    idx = CYCLE_PAGES.index(current)
    return CYCLE_PAGES[(idx + 1) % len(CYCLE_PAGES)]


def prev_page(current: str) -> str:
    if current not in CYCLE_PAGES:
        return CYCLE_PAGES[-1]
    idx = CYCLE_PAGES.index(current)
    return CYCLE_PAGES[(idx - 1) % len(CYCLE_PAGES)]


__all__ = ["CYCLE_PAGES", "PAGES", "next_page", "prev_page"]
