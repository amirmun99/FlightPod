"""GPIO button handling with software debounce + short/long/very-long press
classification.

Concrete GPIO drivers (``gpiozero`` on the Pi, ``None`` on macOS) are
isolated behind :class:`ButtonHandler`. The classifier itself
(:class:`PressClassifier`) is pure and unit-testable.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Iterable

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class PressType(str, enum.Enum):
    SHORT = "short"
    LONG = "long"
    VERY_LONG = "very_long"


@dataclass(frozen=True)
class ButtonEvent:
    button_id: int
    press_type: PressType
    duration_ms: int


# ---------------------------------------------------------------------------
# Pure press classifier
# ---------------------------------------------------------------------------


class PressClassifier:
    """Turn a sequence of (timestamp_s, pressed) edges into press events.

    The classifier is timer-free: callers feed it edges as they happen, and
    flush via :meth:`finalize` when the button is released. Useful in tests.
    """

    def __init__(
        self,
        *,
        debounce_ms: int = 80,
        long_press_ms: int = 800,
        very_long_press_ms: int = 3000,
    ) -> None:
        if debounce_ms < 0:
            raise ValueError("debounce_ms must be >= 0")
        if long_press_ms <= debounce_ms:
            raise ValueError("long_press_ms must be > debounce_ms")
        if very_long_press_ms <= long_press_ms:
            raise ValueError("very_long_press_ms must be > long_press_ms")
        self._debounce_ms = debounce_ms
        self._long_ms = long_press_ms
        self._very_long_ms = very_long_press_ms
        self._press_started_at: float | None = None

    def on_edge(self, *, pressed: bool, timestamp_s: float) -> ButtonEvent | None:
        """Feed one edge. Returns an event when a press completes."""

        if pressed:
            if self._press_started_at is None:
                self._press_started_at = timestamp_s
            return None
        # Release.
        if self._press_started_at is None:
            return None
        duration_ms = int(round((timestamp_s - self._press_started_at) * 1000))
        self._press_started_at = None
        return self._classify(duration_ms)

    def _classify(self, duration_ms: int) -> ButtonEvent | None:
        if duration_ms < self._debounce_ms:
            return None
        if duration_ms < self._long_ms:
            press_type = PressType.SHORT
        elif duration_ms < self._very_long_ms:
            press_type = PressType.LONG
        else:
            press_type = PressType.VERY_LONG
        return ButtonEvent(button_id=0, press_type=press_type, duration_ms=duration_ms)


# ---------------------------------------------------------------------------
# Handler — threadsafe event queue
# ---------------------------------------------------------------------------


@dataclass
class _ButtonState:
    classifier: PressClassifier
    is_pressed: bool = False


class ButtonHandler:
    """Accept edge events from any backend and expose a polled queue.

    The handler is GPIO-agnostic. Concrete backends (gpiozero on Pi)
    forward edge callbacks via :meth:`push_edge`.
    """

    def __init__(
        self,
        *,
        button_ids: Iterable[int],
        debounce_ms: int = 80,
        long_press_ms: int = 800,
        very_long_press_ms: int = 3000,
    ) -> None:
        self._states: dict[int, _ButtonState] = {}
        for bid in button_ids:
            self._states[bid] = _ButtonState(
                classifier=PressClassifier(
                    debounce_ms=debounce_ms,
                    long_press_ms=long_press_ms,
                    very_long_press_ms=very_long_press_ms,
                )
            )
        self._events: Deque[ButtonEvent] = deque(maxlen=64)
        self._lock = threading.Lock()

    def push_edge(self, *, button_id: int, pressed: bool, timestamp_s: float | None = None) -> None:
        ts = timestamp_s if timestamp_s is not None else time.monotonic()
        with self._lock:
            state = self._states.get(button_id)
            if state is None:
                return
            event = state.classifier.on_edge(pressed=pressed, timestamp_s=ts)
            if event is not None:
                # Re-wrap with the actual button_id (classifier defaults to 0).
                self._events.append(
                    ButtonEvent(
                        button_id=button_id,
                        press_type=event.press_type,
                        duration_ms=event.duration_ms,
                    )
                )

    def drain_events(self) -> list[ButtonEvent]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
        return events


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


class NullButtonBackend:
    """No-op backend used on macOS dev or when GPIO isn't available."""

    name = "null"

    def __init__(self, handler: ButtonHandler) -> None:
        self._handler = handler

    def start(self) -> None:
        log.debug("null button backend started (no GPIO)")

    def stop(self) -> None:
        pass


class GpioZeroButtonBackend:
    """gpiozero backend. Imported lazily so it works on macOS."""

    name = "gpiozero"

    def __init__(
        self,
        handler: ButtonHandler,
        *,
        pin_map: dict[int, int],
    ) -> None:
        from gpiozero import Button  # type: ignore[import-untyped]

        self._handler = handler
        self._buttons: dict[int, Button] = {}
        for button_id, gpio_pin in pin_map.items():
            btn = Button(gpio_pin, pull_up=True)
            self._buttons[button_id] = btn

    def start(self) -> None:
        for button_id, btn in self._buttons.items():
            btn.when_pressed = self._make_callback(button_id, pressed=True)
            btn.when_released = self._make_callback(button_id, pressed=False)

    def stop(self) -> None:
        for btn in self._buttons.values():
            btn.when_pressed = None
            btn.when_released = None
            try:
                btn.close()
            except Exception:  # noqa: BLE001
                pass

    def _make_callback(self, button_id: int, *, pressed: bool) -> Callable[[], None]:
        def cb() -> None:
            self._handler.push_edge(button_id=button_id, pressed=pressed)

        return cb


def make_button_backend(
    handler: ButtonHandler,
    *,
    pin_map: dict[int, int] | None = None,
) -> NullButtonBackend | GpioZeroButtonBackend:
    """Choose a backend based on what imports successfully."""

    if not pin_map:
        return NullButtonBackend(handler)
    try:
        return GpioZeroButtonBackend(handler, pin_map=pin_map)
    except (ImportError, OSError, RuntimeError) as exc:
        log.warning("gpiozero unavailable (%s); using null button backend", exc)
        return NullButtonBackend(handler)


__all__ = [
    "ButtonEvent",
    "ButtonHandler",
    "GpioZeroButtonBackend",
    "NullButtonBackend",
    "PressClassifier",
    "PressType",
    "make_button_backend",
]
