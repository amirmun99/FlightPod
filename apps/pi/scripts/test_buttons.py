"""Drain button events from the configured backend.

On the Pi this attaches gpiozero callbacks and prints any short / long /
very-long presses. On macOS it falls back to the null backend and simply
exits.

Usage:
    python apps/pi/scripts/test_buttons.py --pin 4 --button-id 0
    python apps/pi/scripts/test_buttons.py --duration 30
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running without `pip install -e .` from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flightpaper.hardware.buttons import (  # noqa: E402
    ButtonHandler,
    make_button_backend,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Button event smoke test")
    parser.add_argument("--pin", action="append", type=int, default=[])
    parser.add_argument("--button-id", action="append", type=int, default=[])
    parser.add_argument("--duration", type=float, default=15.0, help="seconds")
    parser.add_argument("--debounce-ms", type=int, default=80)
    parser.add_argument("--long-press-ms", type=int, default=800)
    parser.add_argument("--very-long-press-ms", type=int, default=3000)
    args = parser.parse_args()

    if not args.pin:
        # PiSugar 3 default button on GPIO4 (BCM).
        args.pin = [4]
        args.button_id = [0]
    elif len(args.button_id) != len(args.pin):
        args.button_id = list(range(len(args.pin)))

    pin_map = dict(zip(args.button_id, args.pin))
    handler = ButtonHandler(
        button_ids=pin_map.keys(),
        debounce_ms=args.debounce_ms,
        long_press_ms=args.long_press_ms,
        very_long_press_ms=args.very_long_press_ms,
    )
    backend = make_button_backend(handler, pin_map=pin_map)
    backend.start()
    print(f"backend: {backend.__class__.__name__}  pins={pin_map}")
    print(f"Listening for {args.duration:.0f}s ...")

    deadline = time.monotonic() + args.duration
    try:
        while time.monotonic() < deadline:
            for event in handler.drain_events():
                print(
                    f"  button {event.button_id}: "
                    f"{event.press_type.value} ({event.duration_ms} ms)"
                )
            time.sleep(0.05)
    finally:
        backend.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
