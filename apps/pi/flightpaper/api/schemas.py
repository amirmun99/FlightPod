"""Pydantic models for the API request bodies / response shapes.

These mirror ``packages/protocol/api-contract.md``. They're used both for
validation of decrypted plaintext (after the envelope opens) and for
documentation of the public/secure routes.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    ok: bool = True
    device_id: str
    version: str
    uptime_seconds: int


class PairingStatusResponse(BaseModel):
    state: Literal["unpaired", "pairing_pending", "paired"]
    device_id: str
    device_name: str
    pairing_expires_at: int | None = None
    protocol_version: int = 1


# ---------------------------------------------------------------------------
# Pairing handshake (inside envelope, after decryption)
# ---------------------------------------------------------------------------


class PairRequest(BaseModel):
    """Pairing request plaintext (carried inside the envelope ciphertext)."""

    model_config = ConfigDict(extra="forbid")

    client_pub: str = Field(description="Base64url X25519 client public key.")
    app_instance_name: str | None = Field(default=None, max_length=64)
    protocol_version: int = 1


class PairResponseBody(BaseModel):
    ok: bool = True
    device_id: str
    client_id: str
    key_id: Literal["main"] = "main"
    paired_at: int
    session_starts_at_seq: int = 1


# ---------------------------------------------------------------------------
# Secure endpoints
# ---------------------------------------------------------------------------


class LocationRequest(BaseModel):
    """Plaintext carried inside ``POST /api/secure/location``."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    accuracy_m: float | None = Field(default=None, ge=0.0, le=10_000.0)
    altitude_m: float | None = Field(default=None, ge=-500.0, le=20_000.0)
    heading_deg: float | None = Field(default=None, ge=0.0, lt=360.0)
    speed_mps: float | None = Field(default=None, ge=0.0, le=700.0)
    source: Literal["iphone_foreground", "iphone_background"]
    timestamp: int


class LocationResponse(BaseModel):
    accepted: bool = True
    age_seconds: int
    received_at: int


class DisplayPageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: Literal["radar", "closest", "list", "status"]


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfirmRequest(BaseModel):
    """Shared shape for shutdown/reboot/pairing-reset."""

    model_config = ConfigDict(extra="forbid")

    confirm: bool


class ConfigPatchRequest(BaseModel):
    """Whitelisted subset of config that may be patched at runtime.

    Mirrors ``api-contract.md`` §2 ``PATCH /api/secure/config``. Anything
    not listed here is silently ignored to avoid leaking internal config
    surfaces.
    """

    model_config = ConfigDict(extra="ignore")

    # opensky.*
    opensky_update_interval_seconds: int | None = Field(default=None, ge=10, le=600)
    opensky_battery_saver_interval_seconds: int | None = Field(default=None, ge=10, le=3600)
    opensky_max_aircraft_age_seconds: int | None = Field(default=None, ge=10, le=3600)
    opensky_include_ground_aircraft: bool | None = None
    # location.manual.*
    location_manual_enabled: bool | None = None
    location_manual_lat: float | None = Field(default=None, ge=-90, le=90)
    location_manual_lon: float | None = Field(default=None, ge=-180, le=180)
    location_manual_label: str | None = Field(default=None, max_length=32)
    # display.*
    display_partial_refresh: bool | None = None
    display_full_refresh_every: int | None = Field(default=None, ge=1, le=200)
    display_default_page: Literal["radar", "closest", "list", "status"] | None = None
    # ui.*
    ui_radius_km: float | None = Field(default=None, gt=0, le=500)
    ui_overhead_threshold_km: float | None = Field(default=None, gt=0, le=50)
    ui_distance_units: Literal["km", "nm"] | None = None
    ui_altitude_units: Literal["ft", "m"] | None = None
    ui_speed_units: Literal["kt", "mps", "kmh"] | None = None
    # battery.*
    battery_low_percent: int | None = Field(default=None, ge=1, le=99)
    battery_critical_percent: int | None = Field(default=None, ge=1, le=99)
    battery_battery_saver_below_percent: int | None = Field(default=None, ge=1, le=99)
    # buttons.*
    buttons_long_press_ms: int | None = Field(default=None, ge=100, le=10000)
    buttons_very_long_press_ms: int | None = Field(default=None, ge=500, le=30000)


# ---------------------------------------------------------------------------
# Status JSON (spec §16)
# ---------------------------------------------------------------------------


class DeviceStatusBlock(BaseModel):
    id: str
    name: str
    version: str
    uptime_seconds: int


class NetworkStatusBlock(BaseModel):
    wifi_ssid: str | None
    ip_address: str
    internet_ok: bool


class BatteryStatusBlock(BaseModel):
    percent: int | None
    charging: bool | None
    external_power: bool | None
    battery_saver: bool


class LocationStatusBlock(BaseModel):
    source: str | None
    age_seconds: int | None
    accuracy_m: float | None
    fresh: bool
    state: str


class OpenSkyStatusBlock(BaseModel):
    status: str
    last_update_age_seconds: int | None
    aircraft_count: int
    rate_limit_remaining: int | None


class DisplayStatusBlock(BaseModel):
    page: str
    last_refresh_age_seconds: int | None


class StatusResponse(BaseModel):
    device: DeviceStatusBlock
    network: NetworkStatusBlock
    battery: BatteryStatusBlock
    location: LocationStatusBlock
    opensky: OpenSkyStatusBlock
    display: DisplayStatusBlock


# ---------------------------------------------------------------------------
# Error envelope (plaintext inside the encrypted error envelope, or plain
# JSON for envelope-layer errors)
# ---------------------------------------------------------------------------


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_dict(code: str, message: str | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message or code}}
