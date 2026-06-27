"""Configuration loader and typed models for the FlightPaper Pi service.

Source of truth is the Pydantic models below. ``config.example.yml`` mirrors
the defaults so operators have a starting file to edit.

A path resolution order:

1. The path given to :func:`load_config` directly.
2. The ``FLIGHTPAPER_CONFIG`` environment variable.
3. ``/etc/flightpaper/config.yml`` (production).
4. ``$REPO/apps/pi/config.example.yml`` (development fallback).

If none of these exist, defaults are used.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, PositiveFloat, PositiveInt, field_validator


# ---------------------------------------------------------------------------
# Section models
# ---------------------------------------------------------------------------


class AppSection(BaseModel):
    name: str = "FlightPaper"
    version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    timezone: str = "America/Toronto"


class ApiSection(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    require_pairing: bool = True
    secure_envelopes_required: bool = True


class SecuritySection(BaseModel):
    pairing_enabled: bool = True
    pairing_expires_seconds: PositiveInt = 600
    max_pairing_attempts: PositiveInt = 5
    replay_window_seconds: PositiveInt = 120
    allow_unencrypted_debug: bool = False
    secure_dir: str = "/etc/flightpaper/secure"


class OpenSkySection(BaseModel):
    enabled: bool = True
    base_url: str = "https://opensky-network.org/api"
    auth_enabled: bool = False
    update_interval_seconds: PositiveInt = 20
    battery_saver_interval_seconds: PositiveInt = 60
    timeout_seconds: PositiveFloat = 8
    max_aircraft_age_seconds: PositiveInt = 120
    include_ground_aircraft: bool = False
    request_extended: bool = False
    min_interval_seconds: PositiveInt = 10


class ManualLocation(BaseModel):
    enabled: bool = False
    lat: float | None = None
    lon: float | None = None
    label: str = "Manual"

    @field_validator("lat")
    @classmethod
    def _lat_range(cls, v: float | None) -> float | None:
        if v is not None and not -90.0 <= v <= 90.0:
            raise ValueError("lat must be in [-90, 90]")
        return v

    @field_validator("lon")
    @classmethod
    def _lon_range(cls, v: float | None) -> float | None:
        if v is not None and not -180.0 <= v <= 180.0:
            raise ValueError("lon must be in [-180, 180]")
        return v


class LocationSection(BaseModel):
    primary_source: Literal["iphone", "manual"] = "iphone"
    stale_warning_seconds: PositiveInt = 900
    expired_seconds: PositiveInt = 3600
    manual: ManualLocation = Field(default_factory=ManualLocation)


class DisplaySection(BaseModel):
    width: PositiveInt = 250
    height: PositiveInt = 122
    rotation: Literal[0, 90, 180, 270] = 0
    # "waveshare_2in13_v4" (current panels) | "waveshare_2in13_rev2_1" (older V2)
    driver: str = "waveshare_2in13_v4"
    partial_refresh: bool = True
    full_refresh_every: PositiveInt = 10
    max_aircraft_drawn: PositiveInt = 12
    max_labels_drawn: PositiveInt = 3
    default_page: Literal["radar", "closest", "list", "status"] = "radar"


class UISection(BaseModel):
    radius_km: PositiveFloat = 25
    radius_options_km: list[PositiveFloat] = Field(default_factory=lambda: [5, 10, 25, 50, 100])
    overhead_threshold_km: PositiveFloat = 2
    distance_units: Literal["km", "nm"] = "km"
    altitude_units: Literal["ft", "m"] = "ft"
    speed_units: Literal["kt", "mps", "kmh"] = "kt"
    north_up: bool = True
    show_status_bar: bool = True


class BatterySection(BaseModel):
    enabled: bool = True
    provider: Literal["pisugar3", "none"] = "pisugar3"
    pisugar_host: str = "127.0.0.1"
    pisugar_port: int = Field(default=8423, ge=1, le=65535)
    low_percent: int = Field(default=15, ge=0, le=100)
    critical_percent: int = Field(default=5, ge=0, le=100)
    battery_saver_below_percent: int = Field(default=30, ge=0, le=100)
    safe_shutdown_enabled: bool = True


class ButtonsSection(BaseModel):
    enabled: bool = True
    debounce_ms: PositiveInt = 80
    long_press_ms: PositiveInt = 800
    very_long_press_ms: PositiveInt = 3000
    mapping_profile: Literal["minimal", "multi"] = "minimal"


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------


class AppConfig(BaseModel):
    """Root config object. All sections default to spec values."""

    app: AppSection = Field(default_factory=AppSection)
    api: ApiSection = Field(default_factory=ApiSection)
    security: SecuritySection = Field(default_factory=SecuritySection)
    opensky: OpenSkySection = Field(default_factory=OpenSkySection)
    location: LocationSection = Field(default_factory=LocationSection)
    display: DisplaySection = Field(default_factory=DisplaySection)
    ui: UISection = Field(default_factory=UISection)
    battery: BatterySection = Field(default_factory=BatterySection)
    buttons: ButtonsSection = Field(default_factory=ButtonsSection)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


_DEFAULT_PATHS: tuple[Path, ...] = (
    Path("/etc/flightpaper/config.yml"),
    Path(__file__).resolve().parent.parent / "config.example.yml",
)


def _resolve_path(path: str | os.PathLike[str] | None) -> Path | None:
    if path is not None:
        return Path(path)
    env = os.environ.get("FLIGHTPAPER_CONFIG")
    if env:
        return Path(env)
    for candidate in _DEFAULT_PATHS:
        if candidate.exists():
            return candidate
    return None


def load_config(path: str | os.PathLike[str] | None = None) -> AppConfig:
    """Load and validate a FlightPaper config.

    Falls back to defaults if no file is provided or found. Raises
    ``pydantic.ValidationError`` if the file is present but malformed.
    """

    resolved = _resolve_path(path)
    if resolved is None or not resolved.exists():
        return AppConfig()

    with resolved.open("r", encoding="utf-8") as fh:
        raw: Any = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"Config file {resolved} did not parse to a mapping")

    return AppConfig.model_validate(raw)


def dump_config(cfg: AppConfig) -> str:
    """Serialize the effective config to YAML (for debug / API exposure)."""

    return yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False)


__all__ = [
    "AppConfig",
    "AppSection",
    "ApiSection",
    "SecuritySection",
    "OpenSkySection",
    "LocationSection",
    "ManualLocation",
    "DisplaySection",
    "UISection",
    "BatterySection",
    "ButtonsSection",
    "load_config",
    "dump_config",
]
