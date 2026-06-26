"""Tests for the press classifier + button handler queue."""

from __future__ import annotations

import pytest

from flightpaper.hardware.buttons import (
    ButtonHandler,
    PressClassifier,
    PressType,
)


# ---------------------------------------------------------------------------
# PressClassifier (pure)
# ---------------------------------------------------------------------------


def _press(c: PressClassifier, *, start_ms: int, end_ms: int):
    """Helper: simulate a press by feeding two edges."""

    e1 = c.on_edge(pressed=True, timestamp_s=start_ms / 1000)
    assert e1 is None  # Pressing only registers on release.
    return c.on_edge(pressed=False, timestamp_s=end_ms / 1000)


class TestPressClassifier:
    def test_short_press(self) -> None:
        c = PressClassifier(debounce_ms=80, long_press_ms=800, very_long_press_ms=3000)
        event = _press(c, start_ms=0, end_ms=200)
        assert event is not None
        assert event.press_type == PressType.SHORT
        assert event.duration_ms == 200

    def test_long_press(self) -> None:
        c = PressClassifier(debounce_ms=80, long_press_ms=800, very_long_press_ms=3000)
        event = _press(c, start_ms=0, end_ms=1500)
        assert event is not None
        assert event.press_type == PressType.LONG

    def test_very_long_press(self) -> None:
        c = PressClassifier(debounce_ms=80, long_press_ms=800, very_long_press_ms=3000)
        event = _press(c, start_ms=0, end_ms=4000)
        assert event is not None
        assert event.press_type == PressType.VERY_LONG

    def test_debounce_rejects_glitch(self) -> None:
        c = PressClassifier(debounce_ms=80, long_press_ms=800, very_long_press_ms=3000)
        event = _press(c, start_ms=0, end_ms=20)
        assert event is None

    def test_unmatched_release_is_ignored(self) -> None:
        c = PressClassifier(debounce_ms=80, long_press_ms=800, very_long_press_ms=3000)
        # No prior press; releasing should produce nothing.
        assert c.on_edge(pressed=False, timestamp_s=0.0) is None

    def test_double_press_counts_twice(self) -> None:
        c = PressClassifier(debounce_ms=50, long_press_ms=500, very_long_press_ms=2000)
        e1 = _press(c, start_ms=0, end_ms=150)
        e2 = _press(c, start_ms=200, end_ms=350)
        assert e1.press_type == PressType.SHORT  # type: ignore[union-attr]
        assert e2.press_type == PressType.SHORT  # type: ignore[union-attr]

    def test_invalid_thresholds_raise(self) -> None:
        with pytest.raises(ValueError):
            PressClassifier(debounce_ms=-1, long_press_ms=800, very_long_press_ms=3000)
        with pytest.raises(ValueError):
            PressClassifier(debounce_ms=80, long_press_ms=50, very_long_press_ms=3000)
        with pytest.raises(ValueError):
            PressClassifier(debounce_ms=80, long_press_ms=800, very_long_press_ms=500)


# ---------------------------------------------------------------------------
# ButtonHandler queue
# ---------------------------------------------------------------------------


def test_handler_routes_edges_to_correct_button() -> None:
    handler = ButtonHandler(
        button_ids=(0, 1),
        debounce_ms=50,
        long_press_ms=500,
        very_long_press_ms=2000,
    )
    handler.push_edge(button_id=0, pressed=True, timestamp_s=0.0)
    handler.push_edge(button_id=0, pressed=False, timestamp_s=0.150)
    handler.push_edge(button_id=1, pressed=True, timestamp_s=0.0)
    handler.push_edge(button_id=1, pressed=False, timestamp_s=1.0)

    events = handler.drain_events()
    assert {e.button_id for e in events} == {0, 1}
    assert {e.press_type for e in events} == {PressType.SHORT, PressType.LONG}


def test_handler_drain_empties_queue() -> None:
    handler = ButtonHandler(button_ids=(0,), debounce_ms=50, long_press_ms=500, very_long_press_ms=2000)
    handler.push_edge(button_id=0, pressed=True, timestamp_s=0.0)
    handler.push_edge(button_id=0, pressed=False, timestamp_s=0.200)
    assert len(handler.drain_events()) == 1
    assert handler.drain_events() == []


def test_handler_ignores_unknown_buttons() -> None:
    handler = ButtonHandler(button_ids=(0,), debounce_ms=50, long_press_ms=500, very_long_press_ms=2000)
    handler.push_edge(button_id=99, pressed=True, timestamp_s=0.0)
    assert handler.drain_events() == []
