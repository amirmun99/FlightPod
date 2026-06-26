"""Transitions for the display state machine.

Kept pure (operate on the AppState fields directly) so they're easy to
test without spinning up FastAPI / asyncio.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .pages import PAGES, next_page, prev_page

if TYPE_CHECKING:
    from ..api.app_state import AppState

log = logging.getLogger(__name__)


def set_page(state: "AppState", page: str) -> None:
    """Set the current page and request a redraw."""

    if page not in PAGES:
        raise ValueError(f"unknown page: {page!r}")
    if state.current_page == page:
        return
    log.debug("page transition: %s -> %s", state.current_page, page)
    state.current_page = page
    state.force_refresh = True


def cycle_next(state: "AppState") -> None:
    set_page(state, next_page(state.current_page))


def cycle_prev(state: "AppState") -> None:
    set_page(state, prev_page(state.current_page))


def force_refresh(state: "AppState") -> None:
    state.force_refresh = True
    state.force_poll = True


def show_shutdown_confirm(state: "AppState") -> None:
    set_page(state, "shutdown_confirm")


__all__ = [
    "cycle_next",
    "cycle_prev",
    "force_refresh",
    "set_page",
    "show_shutdown_confirm",
]
