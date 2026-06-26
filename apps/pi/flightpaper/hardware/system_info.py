"""System-level introspection: primary IP, Wi-Fi SSID, host uptime.

These helpers degrade gracefully:

* If we can't discover the IP, we return ``"0.0.0.0"`` rather than raise.
* If ``nmcli`` is unavailable (macOS, container, etc.), Wi-Fi SSID is ``None``.
* If ``/proc/uptime`` isn't present (macOS), uptime falls back to a
  process-relative counter.

Phase 6 will replace some of this with battery-aware variants and may add
``hardware/wifi.py`` for SSID change actions.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import socket
import subprocess
import time
from typing import Optional

log = logging.getLogger(__name__)


# Module-load epoch for the macOS fallback path.
_PROCESS_START_MONOTONIC = time.monotonic()


def detect_primary_ip(*, fallback: str = "0.0.0.0") -> str:
    """Return the IP address used to reach the default gateway.

    Uses the classic "open a UDP socket toward a remote, read its local
    name" trick. No packet is actually sent — UDP socket creation is
    enough to populate the source address. Works on both macOS and Linux.
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return str(s.getsockname()[0])
    except OSError as exc:
        log.debug("primary IP detection failed: %s", exc)
        return fallback
    finally:
        s.close()


def detect_wifi_ssid() -> Optional[str]:
    """Return the SSID of the currently-active Wi-Fi link, or ``None``."""

    nmcli = shutil.which("nmcli")
    if not nmcli:
        return None
    try:
        out = subprocess.run(
            [nmcli, "-t", "-f", "active,ssid", "dev", "wifi"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.debug("nmcli failed: %s", exc)
        return None
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        active, _, ssid = line.partition(":")
        if active.strip().lower() == "yes" and ssid:
            return ssid.strip()
    return None


def host_uptime_seconds() -> int:
    """Best-effort host uptime in whole seconds.

    Reads ``/proc/uptime`` on Linux. On macOS (no procfs) falls back to a
    process-relative monotonic counter, which is enough for the status
    page during dev.
    """

    if platform.system() == "Linux":
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as fh:
                return int(float(fh.readline().split()[0]))
        except (OSError, ValueError):
            pass
    return int(time.monotonic() - _PROCESS_START_MONOTONIC)


__all__ = ["detect_primary_ip", "detect_wifi_ssid", "host_uptime_seconds"]
