"""Waveshare 2.13" V4 driver shim.

The 2.13" V4 panel (the revision most commonly shipped today) uses a
different controller init + partial-refresh flow than the V2/Rev2.1, so
it gets its own shim rather than sharing the V2 one. Like the V2 shim we
delegate to Waveshare's ``waveshare_epd`` package (vendored into the venv
by the install script) and import lazily so this file stays safe to
import on macOS dev.

V4 differences vs V2:
* ``init()`` takes no update-mode argument (V2 used ``init(FULL_UPDATE)``).
* Partial refresh is seeded with ``displayPartBaseImage`` once, then driven
  with ``displayPartial`` — there is no ``init(PART_UPDATE)`` toggle.

If anything fails at import or init time the registry catches the
``ImportError`` / ``OSError`` and substitutes the null driver.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from . import epaper

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

log = logging.getLogger(__name__)


class Waveshare213V4Driver:
    """Thin wrapper around ``waveshare_epd.epd2in13_V4``."""

    name = "waveshare_2in13_v4"

    def __init__(self, *, width: int, height: int, rotation: int = 0) -> None:
        self.width = width
        self.height = height
        self.rotation = rotation
        # Import at construction time so make_driver() can detect a missing
        # vendor library on macOS and fall back to the null driver.
        from waveshare_epd import epd2in13_V4  # type: ignore[import-not-found]

        self._module = epd2in13_V4
        self._epd = epd2in13_V4.EPD()
        # Tracks whether the partial-refresh base image has been seeded since
        # the last full refresh. V4 requires displayPartBaseImage() before the
        # first displayPartial().
        self._partial_base_set: bool = False

    # ------------------------------------------------------------------
    # EPaperDriver protocol
    # ------------------------------------------------------------------

    def init(self) -> None:
        self._epd.init()
        self._epd.Clear(0xFF)
        self._partial_base_set = False

    def _to_buffer(self, image: "PILImage") -> Any:
        # The Waveshare buffer routine expects a Pillow ``1`` image at the
        # native resolution.
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        return self._epd.getbuffer(image.convert("1"))

    def display_full(self, image: "PILImage") -> None:
        # Re-init for a clean full refresh, then invalidate the partial base
        # so the next partial reseeds from this frame.
        self._epd.init()
        self._epd.display(self._to_buffer(image))
        self._partial_base_set = False

    def display_partial(self, image: "PILImage") -> None:
        buffer = self._to_buffer(image)
        if not self._partial_base_set:
            # Seed the base image; this also draws the frame.
            self._epd.displayPartBaseImage(buffer)
            self._partial_base_set = True
        else:
            self._epd.displayPartial(buffer)

    def clear(self) -> None:
        self._epd.Clear(0xFF)
        self._partial_base_set = False

    def sleep(self) -> None:
        try:
            self._epd.sleep()
        except Exception as exc:  # noqa: BLE001
            log.warning("waveshare v4 sleep failed: %s", exc)

    def cleanup(self) -> None:
        try:
            self._module.epdconfig.module_exit()
        except Exception as exc:  # noqa: BLE001
            log.warning("waveshare v4 cleanup failed: %s", exc)
        self._partial_base_set = False


# ---------------------------------------------------------------------------
# Register with the driver factory.
# ---------------------------------------------------------------------------


epaper.register_driver(
    "waveshare_2in13_v4",
    lambda w, h, r: Waveshare213V4Driver(width=w, height=h, rotation=r),
)


__all__ = ["Waveshare213V4Driver"]
