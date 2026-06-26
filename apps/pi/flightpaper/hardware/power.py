"""Safe shutdown / reboot helpers used by the secure API endpoints.

We never invoke ``shell=True``. The command list is a hard-coded
allow-list of ``systemctl`` actions. On macOS dev these are no-ops that
log the intended action; the real ``systemctl`` invocation only happens
when the binary is on ``PATH``.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

log = logging.getLogger(__name__)


def _spawn_systemctl(action: str) -> bool:
    """Run ``systemctl <action>`` detached. Returns ``True`` if it spawned."""

    systemctl = shutil.which("systemctl")
    if systemctl is None:
        log.warning("systemctl not on PATH; cannot %s (dev host?)", action)
        return False
    try:
        subprocess.Popen([systemctl, action], shell=False)
        return True
    except (OSError, FileNotFoundError) as exc:
        log.error("systemctl %s failed: %s", action, exc)
        return False


def safe_shutdown() -> bool:
    log.warning("requesting system shutdown")
    return _spawn_systemctl("poweroff")


def safe_reboot() -> bool:
    log.warning("requesting system reboot")
    return _spawn_systemctl("reboot")


__all__ = ["safe_reboot", "safe_shutdown"]
