"""Provider-neutral battery interface."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .pisugar3 import PiSugar3Client

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatteryStatus:
    """One snapshot of the battery state. ``None`` fields mean "unknown"."""

    percent: int | None
    charging: bool | None
    external_power: bool | None

    @property
    def available(self) -> bool:
        return self.percent is not None

    def is_low(self, threshold: int) -> bool:
        return self.percent is not None and self.percent <= threshold

    def is_critical(self, threshold: int) -> bool:
        return self.percent is not None and self.percent <= threshold


@runtime_checkable
class BatteryProvider(Protocol):
    def read(self) -> BatteryStatus: ...


class NullBatteryProvider:
    """Always returns ``(None, None, None)``. Used when no provider exists."""

    name = "none"

    def read(self) -> BatteryStatus:
        return BatteryStatus(percent=None, charging=None, external_power=None)


class PiSugar3BatteryProvider:
    """PiSugar 3 + ``pisugar-server``."""

    name = "pisugar3"

    def __init__(self, client: PiSugar3Client) -> None:
        self._client = client

    def read(self) -> BatteryStatus:
        percent_raw = self._client.battery_percent()
        return BatteryStatus(
            percent=int(round(percent_raw)) if percent_raw is not None else None,
            charging=self._client.charging(),
            external_power=self._client.external_power(),
        )


def make_battery_provider(
    *,
    provider_name: str,
    pisugar_host: str = "127.0.0.1",
    pisugar_port: int = 8423,
) -> BatteryProvider:
    """Build a provider from the ``battery.provider`` config string."""

    if provider_name == "pisugar3":
        return PiSugar3BatteryProvider(
            PiSugar3Client(host=pisugar_host, port=pisugar_port)
        )
    if provider_name in ("none", ""):
        return NullBatteryProvider()
    log.warning("unknown battery provider %r; using none", provider_name)
    return NullBatteryProvider()


__all__ = [
    "BatteryProvider",
    "BatteryStatus",
    "NullBatteryProvider",
    "PiSugar3BatteryProvider",
    "make_battery_provider",
]
