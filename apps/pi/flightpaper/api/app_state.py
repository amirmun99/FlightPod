"""Singleton container for everything the API + background tasks share.

The ``AppState`` is built once in :func:`build_app_state` and stored on
``app.state.flightpaper``. The poller + display loops + request handlers
read and (mutexed) update fields on it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..config import AppConfig, load_config
from ..hardware.battery import (
    BatteryProvider,
    BatteryStatus,
    NullBatteryProvider,
    make_battery_provider,
)
from ..hardware.system_info import detect_primary_ip
from ..location import (
    LocationManager,
    ManualProvider,
    PhoneProvider,
)
from ..opensky import (
    OpenSkyClient,
    OpenSkyProvider,
    RateLimiter,
)
from ..opensky.models import Aircraft
from ..security import (
    DeviceIdentity,
    KeyStore,
    PairingManager,
    ReplayWindow,
    load_or_create_identity,
)

log = logging.getLogger(__name__)


# Page identifiers the UI can be on. Phase 6 fleshes out the renderer.
_VALID_PAGES = ("boot", "pairing", "radar", "closest", "list", "status", "error")


@dataclass
class AppState:
    config: AppConfig
    identity: DeviceIdentity
    key_store: KeyStore
    replay: ReplayWindow
    pairing: PairingManager
    phone_provider: PhoneProvider
    manual_provider: ManualProvider | None
    location: LocationManager
    opensky_client: OpenSkyClient
    opensky_provider: OpenSkyProvider
    battery_provider: BatteryProvider = field(default_factory=NullBatteryProvider)

    # Mutable display state.
    current_page: str = "boot"
    last_refresh_at: float | None = None
    last_aircraft: list[Aircraft] = field(default_factory=list)
    last_aircraft_at: float | None = None
    battery_status: BatteryStatus = field(
        default_factory=lambda: BatteryStatus(None, None, None)
    )

    # Mutable bookkeeping.
    started_at: float = field(default_factory=time.time)
    primary_ip: str = "0.0.0.0"

    # Inter-task signaling.
    force_refresh: bool = False
    force_poll: bool = False
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    # Optional background task handles (set by the lifespan).
    poller_task: asyncio.Task[Any] | None = None
    refresh_task: asyncio.Task[Any] | None = None

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def set_page(self, page: str) -> None:
        if page not in _VALID_PAGES:
            raise ValueError(f"unknown page: {page!r}")
        self.current_page = page
        self.force_refresh = True

    def reset_aircraft(self) -> None:
        self.last_aircraft = []
        self.last_aircraft_at = None


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _resolve_secure_dir(config: AppConfig) -> Path:
    """Resolve the secure directory, honoring ``FLIGHTPAPER_DEV`` for dev."""

    if os.environ.get("FLIGHTPAPER_DEV") == "1":
        return Path.home() / ".flightpaper" / "secure"
    return Path(config.security.secure_dir)


def build_app_state(
    *,
    config_path: str | os.PathLike[str] | None = None,
    secure_dir: Path | None = None,
    opensky_transport: httpx.BaseTransport | None = None,
    host_provider_override: str | None = None,
) -> AppState:
    """Wire up every singleton the API needs.

    Parameters
    ----------
    config_path:        Optional path override; defaults to env / system path.
    secure_dir:         Override for ``security.secure_dir`` (mostly for tests).
    opensky_transport:  ``httpx`` transport for tests (e.g. ``MockTransport``).
    host_provider_override:
        If set, pin the pairing QR's ``host`` field to this string instead of
        the auto-detected primary IP.
    """

    config = load_config(config_path)
    resolved_secure_dir = secure_dir or _resolve_secure_dir(config)
    resolved_secure_dir.mkdir(parents=True, exist_ok=True)

    identity = load_or_create_identity(resolved_secure_dir, device_name=config.app.name)
    key_store = KeyStore(resolved_secure_dir)
    replay = ReplayWindow(replay_window_seconds=config.security.replay_window_seconds)

    primary_ip = detect_primary_ip()

    def _host_provider() -> tuple[str, int]:
        host = host_provider_override or primary_ip
        return host, int(config.api.port)

    pairing = PairingManager(
        secure_dir=resolved_secure_dir,
        identity=identity,
        key_store=key_store,
        replay=replay,
        host_provider=_host_provider,
        expires_seconds=config.security.pairing_expires_seconds,
        max_attempts=config.security.max_pairing_attempts,
    )

    phone_provider = PhoneProvider()
    manual_provider: ManualProvider | None = None
    if config.location.manual.enabled and (
        config.location.manual.lat is not None and config.location.manual.lon is not None
    ):
        manual_provider = ManualProvider(
            lat=float(config.location.manual.lat),
            lon=float(config.location.manual.lon),
            label=config.location.manual.label,
            enabled=True,
        )
    location = LocationManager(
        phone=phone_provider,
        manual=manual_provider,
        primary_source=config.location.primary_source,
        stale_warning_seconds=config.location.stale_warning_seconds,
        expired_seconds=config.location.expired_seconds,
    )

    opensky_client = OpenSkyClient(
        base_url=config.opensky.base_url,
        timeout_s=float(config.opensky.timeout_seconds),
        transport=opensky_transport,
        user_agent=f"FlightPaper/{config.app.version}",
    )
    limiter = RateLimiter(min_interval_s=float(config.opensky.min_interval_seconds))
    opensky_provider = OpenSkyProvider(
        client=opensky_client,
        limiter=limiter,
        cache_ttl_seconds=int(config.opensky.max_aircraft_age_seconds),
    )

    battery_provider: BatteryProvider
    if config.battery.enabled:
        battery_provider = make_battery_provider(
            provider_name=config.battery.provider,
            pisugar_host=config.battery.pisugar_host,
            pisugar_port=int(config.battery.pisugar_port),
        )
    else:
        battery_provider = NullBatteryProvider()

    state = AppState(
        config=config,
        identity=identity,
        key_store=key_store,
        replay=replay,
        pairing=pairing,
        phone_provider=phone_provider,
        manual_provider=manual_provider,
        location=location,
        opensky_client=opensky_client,
        opensky_provider=opensky_provider,
        battery_provider=battery_provider,
        primary_ip=primary_ip,
    )

    # Decide the initial page.
    if pairing.is_paired():
        state.current_page = config.display.default_page
    elif pairing.status()["state"] == "pairing_pending":
        state.current_page = "pairing"
    else:
        # Auto-open a pairing window on first boot so the QR is ready.
        pairing.start()
        state.current_page = "pairing"

    log.info(
        "app state ready: device_id=%s ip=%s page=%s",
        identity.device_id,
        primary_ip,
        state.current_page,
    )
    return state


__all__ = ["AppState", "build_app_state"]
