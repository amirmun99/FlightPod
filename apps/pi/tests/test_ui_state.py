"""Tests for the UI state machine + button → action mapping."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from flightpaper.api.app_state import AppState, build_app_state
from flightpaper.hardware.buttons import ButtonEvent, PressType
from flightpaper.ui import handle_button_event, next_page, prev_page, set_page
from flightpaper.ui.pages import CYCLE_PAGES
from flightpaper.ui.state import cycle_next, cycle_prev, force_refresh, show_shutdown_confirm


def _opensky(_req: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content='{"time": 0, "states": []}')


@pytest.fixture
def state(tmp_path: Path) -> AppState:
    s = build_app_state(
        secure_dir=tmp_path / "secure",
        opensky_transport=httpx.MockTransport(_opensky),
        host_provider_override="172.20.10.4",
    )
    s.current_page = "radar"
    s.force_refresh = False
    yield s
    s.opensky_client.close()


# ---------------------------------------------------------------------------
# Page cycling
# ---------------------------------------------------------------------------


def test_next_page_wraps() -> None:
    assert next_page("radar") == "closest"
    assert next_page(CYCLE_PAGES[-1]) == CYCLE_PAGES[0]


def test_prev_page_wraps() -> None:
    assert prev_page("radar") == CYCLE_PAGES[-1]
    assert prev_page(CYCLE_PAGES[0]) == CYCLE_PAGES[-1]


def test_next_page_from_off_cycle_resets_to_first() -> None:
    assert next_page("boot") == CYCLE_PAGES[0]


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


def test_set_page_marks_refresh(state: AppState) -> None:
    state.force_refresh = False
    set_page(state, "list")
    assert state.current_page == "list"
    assert state.force_refresh is True


def test_set_page_no_change_does_not_force(state: AppState) -> None:
    state.current_page = "radar"
    state.force_refresh = False
    set_page(state, "radar")
    assert state.force_refresh is False


def test_set_page_unknown_raises(state: AppState) -> None:
    with pytest.raises(ValueError):
        set_page(state, "not-a-page")


def test_cycle_next_advances(state: AppState) -> None:
    state.current_page = "radar"
    cycle_next(state)
    assert state.current_page == "closest"


def test_cycle_prev_advances(state: AppState) -> None:
    state.current_page = "radar"
    cycle_prev(state)
    assert state.current_page == "status"


def test_force_refresh_sets_flags(state: AppState) -> None:
    state.force_refresh = False
    state.force_poll = False
    force_refresh(state)
    assert state.force_refresh is True
    assert state.force_poll is True


def test_shutdown_confirm_switches_page(state: AppState) -> None:
    show_shutdown_confirm(state)
    assert state.current_page == "shutdown_confirm"


# ---------------------------------------------------------------------------
# Button mapping
# ---------------------------------------------------------------------------


def _ev(press: PressType, button_id: int = 0) -> ButtonEvent:
    return ButtonEvent(button_id=button_id, press_type=press, duration_ms=200)


def test_short_press_cycles_page(state: AppState) -> None:
    state.current_page = "radar"
    handle_button_event(state, _ev(PressType.SHORT))
    assert state.current_page == "closest"


def test_long_press_forces_refresh(state: AppState) -> None:
    state.force_refresh = False
    state.force_poll = False
    handle_button_event(state, _ev(PressType.LONG))
    assert state.force_refresh is True
    assert state.force_poll is True


def test_very_long_press_shows_shutdown_confirm(state: AppState) -> None:
    handle_button_event(state, _ev(PressType.VERY_LONG))
    assert state.current_page == "shutdown_confirm"
