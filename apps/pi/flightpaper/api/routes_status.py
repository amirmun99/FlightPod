"""Assembly of the ``/api/secure/status`` JSON block (spec §16).

Kept separate so the status shape lives in one place — both the secure
route and any future internal callers (debug script, logs) read from
:func:`build_status_dict`.
"""

from __future__ import annotations

from typing import Any

from ..hardware.system_info import detect_wifi_ssid, host_uptime_seconds
from ..utils.time_utils import age_seconds, now_ts_float
from .app_state import AppState


def build_status_dict(state: AppState) -> dict[str, Any]:
    """Build the JSON shape returned by ``/api/secure/status``."""

    # --- device ----------------------------------------------------------
    device = {
        "id": state.identity.device_id,
        "name": state.identity.device_name,
        "version": state.config.app.version,
        "uptime_seconds": host_uptime_seconds(),
    }

    # --- network ---------------------------------------------------------
    network = {
        "wifi_ssid": detect_wifi_ssid(),
        "ip_address": state.primary_ip,
        # ``internet_ok`` is a best-effort proxy: any successful OpenSky
        # poll in the past TTL implies internet is reachable.
        "internet_ok": state.opensky_provider.status.last_status in ("ok", "stale"),
    }

    # --- battery (PiSugar 3 via pisugar-server; nulls if missing) -------
    bs = state.battery_status
    saver_threshold = int(state.config.battery.battery_saver_below_percent)
    battery_saver = (
        bs.percent is not None and bs.percent <= saver_threshold
    )
    battery = {
        "percent": bs.percent,
        "charging": bs.charging,
        "external_power": bs.external_power,
        "battery_saver": battery_saver,
    }

    # --- location --------------------------------------------------------
    location = state.location.status_dict()

    # --- opensky ---------------------------------------------------------
    opensky_status = state.opensky_provider.status
    opensky = {
        "status": opensky_status.last_status if state.location.current() else "no_location",
        "last_update_age_seconds": opensky_status.last_update_age_seconds,
        "aircraft_count": opensky_status.aircraft_count,
        "rate_limit_remaining": opensky_status.rate_limit_remaining,
    }

    # --- display ---------------------------------------------------------
    last_refresh_age: int | None = None
    if state.last_refresh_at is not None:
        last_refresh_age = age_seconds(int(state.last_refresh_at), now=int(now_ts_float()))
    display = {
        "page": state.current_page,
        "last_refresh_age_seconds": last_refresh_age,
    }

    return {
        "device": device,
        "network": network,
        "battery": battery,
        "location": location,
        "opensky": opensky,
        "display": display,
    }


def build_aircraft_dict(state: AppState, *, limit: int, sort: str) -> dict[str, Any]:
    """Build the JSON for ``GET /api/secure/aircraft``."""

    from ..aircraft.sort import sort_by_distance, sort_overhead_first
    from ..utils.units import (
        km_to_nm,
        meters_to_feet,
        mps_to_fpm,
        mps_to_knots,
    )

    aircraft = list(state.last_aircraft)
    if sort == "overhead":
        aircraft = sort_overhead_first(
            aircraft, overhead_threshold_km=float(state.config.ui.overhead_threshold_km)
        )
    else:
        aircraft = sort_by_distance(aircraft)
    aircraft = aircraft[: max(1, min(limit, 50))]

    out = []
    for ac in aircraft:
        distance_km = ac.distance_km
        # Distance unit conversion is for display only; the renderer uses km
        # internally. Mobile gets values in the configured display units.
        distance_units = state.config.ui.distance_units
        distance_value = distance_km
        if distance_units == "nm" and distance_km is not None:
            distance_value = km_to_nm(distance_km)
        out.append(
            {
                "icao24": ac.icao24,
                "callsign": ac.callsign,
                "origin_country": ac.origin_country,
                "longitude": ac.longitude,
                "latitude": ac.latitude,
                "baro_altitude_ft": meters_to_feet(ac.baro_altitude_m),
                "geo_altitude_ft": meters_to_feet(ac.geo_altitude_m),
                "on_ground": ac.on_ground,
                "velocity_kt": mps_to_knots(ac.velocity_mps),
                "true_track_deg": ac.true_track_deg,
                "vertical_rate_fpm": mps_to_fpm(ac.vertical_rate_mps),
                "squawk": ac.squawk,
                "distance_km": distance_value,
                "bearing_deg": ac.bearing_deg,
                "age_seconds": ac.age_seconds,
            }
        )

    return {
        "aircraft": out,
        "as_of_seconds": state.opensky_provider.status.last_update_age_seconds,
        "count": len(out),
        "radius_km": float(state.config.ui.radius_km),
    }


__all__ = ["build_aircraft_dict", "build_status_dict"]
