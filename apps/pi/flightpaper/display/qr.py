"""QR rendering for the ePaper pairing page.

The Waveshare 2.13" is 250x122 pixels and the QR must share the screen
with text. We target ≤ 120x120 px with a 4-module quiet zone (the QR-spec
minimum) so close-up phone scans decode reliably.

To keep the QR scannable the pairing payload is kept small (no IPv6, short
device names) and the QR uses error-correction level ``L`` (low). If
payloads grow we should re-evaluate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import qrcode  # type: ignore[import-untyped]
from qrcode.constants import ERROR_CORRECT_L

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage


# Target footprint constraints from spec §11.
TARGET_MAX_PX: int = 120


class QrRenderError(Exception):
    """Couldn't fit the requested QR into the size budget."""


def render_qr_image(
    text: str,
    *,
    target_px: int = TARGET_MAX_PX,
    border_modules: int = 4,
) -> "PILImage":
    """Render ``text`` as a 1-bit PIL image no larger than ``target_px``."""

    if not text:
        raise QrRenderError("empty QR text")

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_L,
        box_size=1,
        border=border_modules,
    )
    qr.add_data(text)
    try:
        qr.make(fit=True)
    except (ValueError, qrcode.exceptions.DataOverflowError) as exc:
        raise QrRenderError(
            f"QR payload too large to encode: {exc}; shorten the pairing payload"
        ) from exc
    # Total modules = (qr.modules_count) + 2 * border (added by qrcode itself).
    base = qr.make_image(fill_color="black", back_color="white").convert("1")

    raw_size = base.size[0]
    if raw_size > target_px:
        # If we'd shrink below 1 px per module the QR becomes unscannable.
        # Bail out so the caller can adjust the payload instead of silently
        # producing a useless image.
        raise QrRenderError(
            f"QR would not fit in {target_px}px (raw {raw_size}px); "
            f"shorten the pairing payload"
        )

    if raw_size == target_px:
        return base

    # Upscale with nearest neighbor so module edges stay crisp.
    return base.resize((target_px, target_px))


def render_pairing_qr(uri: str, *, target_px: int = TARGET_MAX_PX) -> "PILImage":
    """Convenience wrapper for :func:`render_qr_image` with the pairing URI."""

    return render_qr_image(uri, target_px=target_px)


__all__ = ["QrRenderError", "TARGET_MAX_PX", "render_pairing_qr", "render_qr_image"]
