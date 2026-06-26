"""Pillow primitives for the recurring glyphs.

Everything draws onto a passed-in :class:`PIL.ImageDraw.ImageDraw` so
layouts can compose without owning their own image.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.ImageDraw import ImageDraw


BLACK: int = 0
WHITE: int = 1


# ---------------------------------------------------------------------------
# Aircraft triangle (pointing toward its track)
# ---------------------------------------------------------------------------


def aircraft_triangle(
    draw: "ImageDraw",
    *,
    center: tuple[int, int],
    heading_deg: float | None,
    size_px: int = 5,
    color: int = BLACK,
) -> None:
    """Draw a small triangle marker pointing toward ``heading_deg`` (0 = N)."""

    cx, cy = center
    # If heading is unknown, draw a small filled square as a generic marker.
    if heading_deg is None:
        draw.rectangle(
            (cx - size_px // 2, cy - size_px // 2, cx + size_px // 2, cy + size_px // 2),
            fill=color,
        )
        return

    theta = math.radians(heading_deg % 360.0)
    # Tip of the triangle (nose, in track direction).
    nose = (
        cx + math.sin(theta) * size_px,
        cy - math.cos(theta) * size_px,
    )
    # Two trailing corners 140° behind the nose.
    spread = math.radians(140.0)
    left = (
        cx + math.sin(theta + spread) * size_px,
        cy - math.cos(theta + spread) * size_px,
    )
    right = (
        cx + math.sin(theta - spread) * size_px,
        cy - math.cos(theta - spread) * size_px,
    )
    draw.polygon([nose, left, right], fill=color, outline=color)


# ---------------------------------------------------------------------------
# Battery icon
# ---------------------------------------------------------------------------


def battery_icon(
    draw: "ImageDraw",
    *,
    top_left: tuple[int, int],
    width: int = 18,
    height: int = 8,
    percent: int | None,
    charging: bool = False,
) -> None:
    """Draw a battery silhouette with a fill proportional to ``percent``."""

    x, y = top_left
    # Outer rectangle (1px outline).
    draw.rectangle((x, y, x + width - 3, y + height - 1), outline=BLACK)
    # Cap on the right.
    cap_height = max(2, height - 4)
    draw.rectangle(
        (x + width - 3, y + (height - cap_height) // 2, x + width - 1, y + (height + cap_height) // 2),
        fill=BLACK,
    )
    # Fill.
    if percent is None:
        # Drawn as cross-hatched (no info).
        draw.line((x + 1, y + height - 2, x + width - 4, y + 1), fill=BLACK)
        return
    fill_px = max(0, min(width - 5, int(round((width - 5) * percent / 100.0))))
    if fill_px > 0:
        draw.rectangle(
            (x + 1, y + 1, x + 1 + fill_px, y + height - 2),
            fill=BLACK,
        )
    if charging and width >= 10:
        # Lightning bolt over the centre.
        mid_x = x + width // 2 - 1
        mid_y = y + height // 2
        draw.line(
            (mid_x, y + 1, mid_x - 1, mid_y, mid_x + 2, mid_y, mid_x + 1, y + height - 2),
            fill=WHITE,
        )


# ---------------------------------------------------------------------------
# Wi-Fi indicator
# ---------------------------------------------------------------------------


def wifi_icon(
    draw: "ImageDraw",
    *,
    top_left: tuple[int, int],
    connected: bool,
    size_px: int = 9,
) -> None:
    """Draw a tiny wifi arc icon. ``connected=False`` overlays an X."""

    x, y = top_left
    # Three nested arcs, top-half.
    for radius in (size_px, size_px - 3, size_px - 6):
        if radius < 2:
            continue
        bbox = (
            x + size_px - radius,
            y + size_px - radius,
            x + size_px + radius,
            y + size_px + radius,
        )
        draw.arc(bbox, start=200, end=340, fill=BLACK, width=1)
    # Antenna dot.
    draw.rectangle((x + size_px - 1, y + size_px - 1, x + size_px, y + size_px), fill=BLACK)
    if not connected:
        # Slash across the icon.
        draw.line(
            (x, y + 2 * size_px, x + 2 * size_px, y),
            fill=BLACK,
            width=1,
        )


# ---------------------------------------------------------------------------
# Radar ring + tick marks
# ---------------------------------------------------------------------------


def radar_ring(
    draw: "ImageDraw",
    *,
    center: tuple[int, int],
    radius: int,
    color: int = BLACK,
) -> None:
    """Outer radar circle plus a small N indicator above it."""

    cx, cy = center
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        outline=color,
    )
    # Inner half-radius ring (dotted).
    inner = radius // 2
    for theta_deg in range(0, 360, 18):
        t = math.radians(theta_deg)
        px = cx + int(round(math.sin(t) * inner))
        py = cy - int(round(math.cos(t) * inner))
        draw.point((px, py), fill=color)
    # User dot.
    draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=color)
    # N marker outside the ring (no rotation: north-up).
    draw.text((cx - 3, cy - radius - 11), "N", fill=color)


def cardinal_tick(
    draw: "ImageDraw",
    *,
    center: tuple[int, int],
    radius: int,
    bearing_deg: float,
    length_px: int = 3,
    color: int = BLACK,
) -> None:
    cx, cy = center
    t = math.radians(bearing_deg % 360.0)
    inner_x = cx + math.sin(t) * (radius - length_px)
    inner_y = cy - math.cos(t) * (radius - length_px)
    outer_x = cx + math.sin(t) * radius
    outer_y = cy - math.cos(t) * radius
    draw.line(
        (int(round(inner_x)), int(round(inner_y)), int(round(outer_x)), int(round(outer_y))),
        fill=color,
    )


__all__ = [
    "BLACK",
    "WHITE",
    "aircraft_triangle",
    "battery_icon",
    "cardinal_tick",
    "radar_ring",
    "wifi_icon",
]
