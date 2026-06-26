"""Display subsystem.

Phase 4 only populates :mod:`flightpaper.display.qr` (QR code rendering
for the pairing page). The full layout/render pipeline arrives in Phase 6.
"""

from .qr import QrRenderError, render_pairing_qr, render_qr_image

__all__ = ["QrRenderError", "render_pairing_qr", "render_qr_image"]
