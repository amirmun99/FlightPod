"""User-interface state machine + input handlers.

* :mod:`pages` — page identifiers and the cycle order for next/prev.
* :mod:`state` — pure helpers that transition the current page.
* :mod:`input` — adapter from button events to page transitions / actions.
"""

from .input import handle_button_event
from .pages import CYCLE_PAGES, PAGES, next_page, prev_page
from .state import set_page

__all__ = [
    "CYCLE_PAGES",
    "PAGES",
    "handle_button_event",
    "next_page",
    "prev_page",
    "set_page",
]
