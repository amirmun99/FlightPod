"""Font loading. Tries DejaVu Sans first (standard on Raspberry Pi OS) and
falls back to Pillow's bundled bitmap font so rendering still works on a
fresh macOS install without extra setup.

Font sizes used across pages:

* ``status``: 8pt — the top status bar.
* ``label``:  10pt — body text on most pages.
* ``value``:  14pt — primary value (callsign, distance, headline).
* ``title``:  16pt — page titles (PAIR, STATUS, etc.).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

log = logging.getLogger(__name__)


# Ordered candidate paths. The first one that loads wins.
_CANDIDATES: tuple[str, ...] = (
    # Raspberry Pi OS / Debian.
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    # Standard Linux locations.
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    # Bundled (added by `install.sh` later if needed).
    str(Path(__file__).parent / "assets" / "DejaVuSans.ttf"),
    # macOS dev fallback.
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

_BOLD_CANDIDATES: tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    str(Path(__file__).parent / "assets" / "DejaVuSans-Bold.ttf"),
    "/System/Library/Fonts/Helvetica.ttc",  # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


@lru_cache(maxsize=16)
def _load(size: int, bold: bool = False) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    candidates = _BOLD_CANDIDATES if bold else _CANDIDATES
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue
    log.debug("no TrueType font found; using Pillow default (size=%d)", size)
    # Pillow 10+ supports a size argument on load_default.
    try:
        return ImageFont.load_default(size=size)  # type: ignore[call-arg]
    except TypeError:
        return ImageFont.load_default()


def status_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    return _load(10)


def label_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    return _load(12)


def value_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    return _load(16, bold=True)


def title_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    return _load(18, bold=True)


__all__ = ["label_font", "status_font", "title_font", "value_font"]
