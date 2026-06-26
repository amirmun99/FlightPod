"""Client for the local ``pisugar-server`` TCP socket.

The PiSugar 3 ships with a system service that listens on
``127.0.0.1:8423`` and accepts a simple line-oriented command protocol:

    > get battery
    < battery: 82.5
    > get battery_charging
    < battery_charging: false
    > get battery_power_plugged
    < battery_power_plugged: true

If the server isn't running (e.g. PiSugar wasn't installed, or we're on
macOS), every method returns ``None`` and logs a single warning. The Pi
keeps running normally and the status bar shows ``BAT --``.
"""

from __future__ import annotations

import logging
import socket
from contextlib import contextmanager
from typing import Iterator, Optional

log = logging.getLogger(__name__)


class PiSugar3Client:
    """Tiny line-protocol client for the PiSugar 3 server."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8423,
        timeout: float = 1.0,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._warned_unavailable = False

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[socket.socket]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self._timeout)
        try:
            sock.connect((self._host, self._port))
            yield sock
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _query(self, command: str) -> Optional[str]:
        try:
            with self._connect() as sock:
                sock.sendall((command.strip() + "\n").encode("ascii"))
                buf = bytearray()
                while True:
                    chunk = sock.recv(256)
                    if not chunk:
                        break
                    buf.extend(chunk)
                    if b"\n" in buf:
                        break
        except OSError as exc:
            if not self._warned_unavailable:
                log.warning(
                    "pisugar-server unavailable at %s:%d (%s)",
                    self._host,
                    self._port,
                    exc,
                )
                self._warned_unavailable = True
            return None
        text = buf.split(b"\n", 1)[0].decode("ascii", errors="replace").strip()
        return text or None

    @staticmethod
    def _split(response: str | None) -> str | None:
        if response is None or ":" not in response:
            return None
        return response.split(":", 1)[1].strip()

    # ------------------------------------------------------------------
    # Typed accessors
    # ------------------------------------------------------------------

    def battery_percent(self) -> float | None:
        value = self._split(self._query("get battery"))
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def charging(self) -> bool | None:
        value = self._split(self._query("get battery_charging"))
        if value is None:
            return None
        return value.lower() in ("true", "1", "yes")

    def external_power(self) -> bool | None:
        # PiSugar reports this as ``battery_power_plugged``.
        value = self._split(self._query("get battery_power_plugged"))
        if value is None:
            return None
        return value.lower() in ("true", "1", "yes")

    def safe_shutdown(self) -> bool:
        """Ask the PiSugar server to power down the rail safely."""

        return self._query("rtc_alarm_set 0") is not None


__all__ = ["PiSugar3Client"]
