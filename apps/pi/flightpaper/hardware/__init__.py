"""Hardware-facing modules.

* :mod:`system_info` — primary IP, Wi-Fi SSID, host uptime (Phase 5).
* :mod:`pisugar3` — TCP client for ``pisugar-server`` on 127.0.0.1:8423.
* :mod:`battery` — provider-agnostic battery interface.
* :mod:`buttons` — debounced press classification + gpiozero shim.
* :mod:`wifi` — read-only Wi-Fi helpers.
* :mod:`power` — safe shutdown / reboot via ``systemctl``.
"""

from .battery import (
    BatteryProvider,
    BatteryStatus,
    NullBatteryProvider,
    PiSugar3BatteryProvider,
    make_battery_provider,
)
from .buttons import (
    ButtonEvent,
    ButtonHandler,
    GpioZeroButtonBackend,
    NullButtonBackend,
    PressClassifier,
    PressType,
    make_button_backend,
)
from .pisugar3 import PiSugar3Client
from .power import safe_reboot, safe_shutdown
from .system_info import detect_primary_ip, detect_wifi_ssid, host_uptime_seconds
from .wifi import current_ssid

__all__ = [
    "BatteryProvider",
    "BatteryStatus",
    "ButtonEvent",
    "ButtonHandler",
    "GpioZeroButtonBackend",
    "NullBatteryProvider",
    "NullButtonBackend",
    "PiSugar3BatteryProvider",
    "PiSugar3Client",
    "PressClassifier",
    "PressType",
    "current_ssid",
    "detect_primary_ip",
    "detect_wifi_ssid",
    "host_uptime_seconds",
    "make_battery_provider",
    "make_button_backend",
    "safe_reboot",
    "safe_shutdown",
]
