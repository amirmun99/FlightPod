"""Waveshare 2.13" V2 / Rev2.1 driver shim.

Rather than reimplement the SSD1680 init sequence here, we delegate to
Waveshare's ``waveshare_epd`` package. That package is not on PyPI, so the
install script vendors it into the venv from Waveshare's e-Paper repo. The
module is imported lazily so this file is safe to import on macOS dev.

If anything fails at import or init time the registry catches the
``ImportError`` / ``OSError`` and substitutes the null driver — the rest
of the system never crashes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from . import epaper

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Concrete driver
# ---------------------------------------------------------------------------


class Waveshare213V2Rev21Driver:
    """Thin wrapper around ``waveshare_epd.epd2in13_V2``."""

    name = "waveshare_2in13_rev2_1"

    def __init__(self, *, width: int, height: int, rotation: int = 0) -> None:
        self.width = width
        self.height = height
        self.rotation = rotation
        # Import at construction time so make_driver() can detect missing
        # vendor library on macOS and fall back to the null driver.
        from waveshare_epd import epd2in13_V2  # type: ignore[import-not-found]

        self._module = epd2in13_V2
        self._epd = epd2in13_V2.EPD()
        self._partial_initialised: bool = False

    # ------------------------------------------------------------------
    # EPaperDriver protocol
    # ------------------------------------------------------------------

    def init(self) -> None:
        self._epd.init(self._epd.FULL_UPDATE)
        self._epd.Clear(0xFF)

    def _to_buffer(self, image: "PILImage") -> Any:
        # The Waveshare buffer routine expects a Pillow ``1`` image at the
        # native resolution.
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
        return self._epd.getbuffer(image.convert("1"))

    def display_full(self, image: "PILImage") -> None:
        if self._partial_initialised:
            self._epd.init(self._epd.FULL_UPDATE)
            self._partial_initialised = False
        self._epd.display(self._to_buffer(image))

    def display_partial(self, image: "PILImage") -> None:
        if not self._partial_initialised:
            self._epd.init(self._epd.PART_UPDATE)
            self._partial_initialised = True
        self._epd.displayPartial(self._to_buffer(image))

    def clear(self) -> None:
        self._epd.Clear(0xFF)

    def sleep(self) -> None:
        try:
            self._epd.sleep()
        except Exception as exc:  # noqa: BLE001
            log.warning("waveshare sleep failed: %s", exc)

    def cleanup(self) -> None:
        try:
            self._module.epdconfig.module_exit()
        except Exception as exc:  # noqa: BLE001
            log.warning("waveshare cleanup failed: %s", exc)
        self._partial_initialised = False


# ---------------------------------------------------------------------------
# Register with the driver factory.
# ---------------------------------------------------------------------------


epaper.register_driver(
    "waveshare_2in13_rev2_1",
    lambda w, h, r: Waveshare213V2Rev21Driver(width=w, height=h, rotation=r),
)


__all__ = ["Waveshare213V2Rev21Driver"]
