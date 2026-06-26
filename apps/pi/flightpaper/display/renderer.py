"""Top-level page dispatcher.

The render path is intentionally narrow: build a fresh 1-bit canvas at the
configured display size, look up the page renderer, call it, optionally
rotate, return.

Errors raised by individual layouts are caught and downgraded into an
``error`` page so the display never blanks mid-flight.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from PIL import Image, ImageDraw

from . import layouts

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

    from ..api.app_state import AppState

log = logging.getLogger(__name__)


PageRenderer = Callable[[ImageDraw.ImageDraw, "PILImage", "AppState"], None]

_PAGES: dict[str, PageRenderer] = {
    "boot": layouts.render_boot,
    "pairing": layouts.render_pairing,
    "radar": layouts.render_radar,
    "closest": layouts.render_closest,
    "list": layouts.render_list,
    "status": layouts.render_status,
    "shutdown_confirm": layouts.render_shutdown_confirm,
}


def render_page(state: "AppState", page: str | None = None) -> "PILImage":
    """Render the named page (or ``state.current_page`` if omitted)."""

    name = page or state.current_page
    width = int(state.config.display.width)
    height = int(state.config.display.height)
    rotation = int(state.config.display.rotation)

    image = Image.new("1", (width, height), color=1)  # 1 = white background
    draw = ImageDraw.Draw(image)

    handler = _PAGES.get(name)
    try:
        if handler is None:
            layouts.render_error(
                draw,
                image,
                state,
                kind="render_error",
                detail_override=(f"unknown page: {name}",),
            )
        else:
            handler(draw, image, state)
    except Exception as exc:  # noqa: BLE001 - rendering must never crash
        log.exception("page %s render failed", name)
        # Reset the canvas so we don't show a half-baked frame.
        image = Image.new("1", (width, height), color=1)
        draw = ImageDraw.Draw(image)
        layouts.render_error(
            draw,
            image,
            state,
            kind="render_error",
            detail_override=(str(exc)[:30],),
        )

    if rotation in (90, 180, 270):
        # PIL uses counter-clockwise rotation; the on-device rotation is
        # logical (physical orientation of the screen).
        image = image.rotate(-rotation, expand=True)

    return image


def list_pages() -> list[str]:
    """Names supported by :func:`render_page`."""

    return list(_PAGES.keys())


__all__ = ["list_pages", "render_page"]
