"""Smoke-test the configured ePaper driver.

On the Pi this draws a checkerboard + a "FlightPaper" banner via the
configured driver. On macOS it falls back to the null driver and just
writes the rendered PNG to disk.

Usage:
    python apps/pi/scripts/test_display.py
    python apps/pi/scripts/test_display.py --driver waveshare_2in13_rev2_1
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# Allow running without `pip install -e .` from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from flightpaper.display.epaper import make_driver  # noqa: E402
from flightpaper.display.fonts import title_font  # noqa: E402


def _build_test_image(width: int, height: int) -> Image.Image:
    image = Image.new("1", (width, height), color=1)
    draw = ImageDraw.Draw(image)
    # 8x8 checkerboard.
    block = 8
    for y in range(0, height, block):
        for x in range(0, width, block):
            if (x // block + y // block) % 2 == 0:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=0)
    # Banner over the middle.
    draw.rectangle((10, height // 2 - 12, width - 10, height // 2 + 12), fill=1)
    draw.text((16, height // 2 - 8), "FlightPaper test", font=title_font(), fill=0)
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="ePaper smoke test")
    parser.add_argument("--driver", default="waveshare_2in13_v4")
    parser.add_argument("--width", type=int, default=250)
    parser.add_argument("--height", type=int, default=122)
    parser.add_argument("--rotation", type=int, default=0)
    parser.add_argument(
        "--png-out",
        type=Path,
        default=Path(tempfile.gettempdir()) / "flightpaper_display_test.png",
    )
    args = parser.parse_args()

    image = _build_test_image(args.width, args.height)
    image.save(args.png_out)
    print(f"PNG saved to {args.png_out}")

    driver = make_driver(
        args.driver, width=args.width, height=args.height, rotation=args.rotation
    )
    print(f"driver: {driver.__class__.__name__}")
    driver.init()
    driver.display_full(image)
    print("display_full() called")
    driver.sleep()
    driver.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
