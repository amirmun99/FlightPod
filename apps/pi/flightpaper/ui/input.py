"""Map :class:`ButtonEvent` to state-machine transitions.

Spec §17 default mapping (single button):

* short press      → cycle to next page
* long press       → force refresh
* very long press  → shutdown confirmation prompt
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..hardware.buttons import ButtonEvent, PressType
from . import state as ui_state

if TYPE_CHECKING:
    from ..api.app_state import AppState

log = logging.getLogger(__name__)


def handle_button_event(state: "AppState", event: ButtonEvent) -> None:
    """Apply one button event. Multi-button profiles can hook here later."""

    profile = state.config.buttons.mapping_profile

    if profile == "minimal" or event.button_id == 0:
        _handle_single_button(state, event)
        return

    # Multi-button profile (spec §25):
    if event.button_id == 0:
        ui_state.cycle_next(state)
    elif event.button_id == 1:
        ui_state.cycle_prev(state)
    elif event.button_id == 2:
        ui_state.force_refresh(state)
    elif event.button_id == 3:
        ui_state.show_shutdown_confirm(state)
    else:
        log.debug("unmapped button %d", event.button_id)


def _handle_single_button(state: "AppState", event: ButtonEvent) -> None:
    if event.press_type == PressType.SHORT:
        ui_state.cycle_next(state)
    elif event.press_type == PressType.LONG:
        ui_state.force_refresh(state)
    elif event.press_type == PressType.VERY_LONG:
        ui_state.show_shutdown_confirm(state)


__all__ = ["handle_button_event"]
