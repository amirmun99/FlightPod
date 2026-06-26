"""Minimal Wi-Fi helpers — currently read-only.

Phase 6 only exposes :func:`current_ssid`. SSID-change actions
(``nmcli dev wifi connect ...``) are deferred to a future phase since the
mobile MVP doesn't require them.
"""

from __future__ import annotations

import logging

from .system_info import detect_wifi_ssid

log = logging.getLogger(__name__)


def current_ssid() -> str | None:
    """Return the SSID of the active Wi-Fi link, or ``None`` if unknown."""

    return detect_wifi_ssid()


__all__ = ["current_ssid"]
