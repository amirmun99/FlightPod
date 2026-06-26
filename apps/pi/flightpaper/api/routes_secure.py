"""``/api/secure/*`` — every endpoint requires a verified secure envelope.

Each route:

1. Opens the envelope via :func:`open_secure_envelope` (raises HTTP errors
   on failure — the route handler never sees a bad envelope).
2. Parses the plaintext as the expected Pydantic model.
3. Performs the side effect (update location, change page, etc.).
4. Builds a response body and seals it via :func:`seal_response`.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from ..config import AppConfig
from ..location.payload import (
    InvalidLocationPayload,
    validate_location_payload,
)
from ..utils.time_utils import now_ts, now_ts_float
from .app_state import AppState
from .auth import (
    get_state,
    http_status_for,
    open_secure_envelope,
    parse_plaintext_json,
    seal_response,
)
from .routes_status import build_aircraft_dict, build_status_dict
from .schemas import (
    ConfigPatchRequest,
    ConfirmRequest,
    DisplayPageRequest,
    LocationRequest,
    LocationResponse,
    StatusResponse,
    error_dict,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/secure", tags=["secure"])


def _bad_request(reason: str = "invalid_request") -> HTTPException:
    return HTTPException(
        status_code=http_status_for("invalid_request"),
        detail=error_dict(reason),
    )


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


@router.post("/location")
async def post_location(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    raw = parse_plaintext_json(opened.plaintext)

    # Pydantic shape gate, then deeper sanity rules.
    try:
        LocationRequest.model_validate(raw)
    except ValidationError as exc:
        log.debug("location request validation failed: %s", exc)
        raise _bad_request()
    try:
        payload = validate_location_payload(raw, now=now_ts())
    except InvalidLocationPayload as exc:
        log.debug("location payload rejected: %s", exc)
        raise _bad_request()

    now = now_ts()
    state.location.apply_phone_payload(payload, now=now)
    state.force_refresh = True

    body = LocationResponse(
        accepted=True,
        age_seconds=max(0, now - payload.timestamp),
        received_at=now,
    ).model_dump(mode="json")
    return seal_response(state=state, request=request, opened=opened, body=body)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_status(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    body = build_status_dict(state)
    # Round-trip through StatusResponse to validate the shape we ship.
    StatusResponse.model_validate(body)
    return seal_response(state=state, request=request, opened=opened, body=body)


# ---------------------------------------------------------------------------
# Aircraft list
# ---------------------------------------------------------------------------


@router.get("/aircraft")
async def get_aircraft(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    sort: Literal["distance", "overhead", "altitude"] = Query(default="distance"),
) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    body = build_aircraft_dict(state, limit=limit, sort=sort)
    return seal_response(state=state, request=request, opened=opened, body=body)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _config_to_wire(cfg: AppConfig) -> dict[str, Any]:
    return cfg.model_dump(mode="json")


def _apply_patch(state: AppState, patch: ConfigPatchRequest) -> None:
    """Apply whitelisted patch fields to the live config + dependent singletons."""

    cfg = state.config

    if patch.opensky_update_interval_seconds is not None:
        cfg.opensky.update_interval_seconds = patch.opensky_update_interval_seconds
    if patch.opensky_battery_saver_interval_seconds is not None:
        cfg.opensky.battery_saver_interval_seconds = patch.opensky_battery_saver_interval_seconds
    if patch.opensky_max_aircraft_age_seconds is not None:
        cfg.opensky.max_aircraft_age_seconds = patch.opensky_max_aircraft_age_seconds
    if patch.opensky_include_ground_aircraft is not None:
        cfg.opensky.include_ground_aircraft = patch.opensky_include_ground_aircraft

    if patch.location_manual_enabled is not None:
        cfg.location.manual.enabled = patch.location_manual_enabled
        if state.manual_provider is not None:
            state.manual_provider.set_enabled(patch.location_manual_enabled)
    if patch.location_manual_lat is not None:
        cfg.location.manual.lat = patch.location_manual_lat
    if patch.location_manual_lon is not None:
        cfg.location.manual.lon = patch.location_manual_lon
    if patch.location_manual_label is not None:
        cfg.location.manual.label = patch.location_manual_label
    if (
        state.manual_provider is not None
        and patch.location_manual_lat is not None
        and patch.location_manual_lon is not None
    ):
        state.manual_provider.update(
            lat=patch.location_manual_lat,
            lon=patch.location_manual_lon,
            label=patch.location_manual_label,
        )

    if patch.display_partial_refresh is not None:
        cfg.display.partial_refresh = patch.display_partial_refresh
    if patch.display_full_refresh_every is not None:
        cfg.display.full_refresh_every = patch.display_full_refresh_every
    if patch.display_default_page is not None:
        cfg.display.default_page = patch.display_default_page

    if patch.ui_radius_km is not None:
        cfg.ui.radius_km = patch.ui_radius_km
    if patch.ui_overhead_threshold_km is not None:
        cfg.ui.overhead_threshold_km = patch.ui_overhead_threshold_km
    if patch.ui_distance_units is not None:
        cfg.ui.distance_units = patch.ui_distance_units
    if patch.ui_altitude_units is not None:
        cfg.ui.altitude_units = patch.ui_altitude_units
    if patch.ui_speed_units is not None:
        cfg.ui.speed_units = patch.ui_speed_units

    if patch.battery_low_percent is not None:
        cfg.battery.low_percent = patch.battery_low_percent
    if patch.battery_critical_percent is not None:
        cfg.battery.critical_percent = patch.battery_critical_percent
    if patch.battery_battery_saver_below_percent is not None:
        cfg.battery.battery_saver_below_percent = patch.battery_battery_saver_below_percent

    if patch.buttons_long_press_ms is not None:
        cfg.buttons.long_press_ms = patch.buttons_long_press_ms
    if patch.buttons_very_long_press_ms is not None:
        cfg.buttons.very_long_press_ms = patch.buttons_very_long_press_ms


@router.get("/config")
async def get_config(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    return seal_response(
        state=state, request=request, opened=opened, body=_config_to_wire(state.config)
    )


@router.patch("/config")
async def patch_config(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    raw = parse_plaintext_json(opened.plaintext)
    try:
        patch = ConfigPatchRequest.model_validate(raw)
    except ValidationError as exc:
        log.debug("config patch invalid: %s", exc)
        raise _bad_request()
    _apply_patch(state, patch)
    return seal_response(
        state=state, request=request, opened=opened, body=_config_to_wire(state.config)
    )


# ---------------------------------------------------------------------------
# Display page + refresh
# ---------------------------------------------------------------------------


@router.post("/display/page")
async def set_page(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    raw = parse_plaintext_json(opened.plaintext)
    try:
        req = DisplayPageRequest.model_validate(raw)
    except ValidationError:
        raise _bad_request()
    state.set_page(req.page)
    return seal_response(
        state=state,
        request=request,
        opened=opened,
        body={"ok": True, "page": req.page},
    )


@router.post("/refresh")
async def force_refresh(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    state.force_refresh = True
    state.force_poll = True
    return seal_response(
        state=state, request=request, opened=opened, body={"ok": True}
    )


# ---------------------------------------------------------------------------
# System: shutdown + reboot
# ---------------------------------------------------------------------------


_SHUTDOWN_GRACE_SECONDS = 5


async def _delayed_system_action(args: list[str], delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        subprocess.Popen(args, shell=False)  # noqa: S603 - explicit args list
    except (OSError, FileNotFoundError) as exc:
        log.error("system action %s failed: %s", args, exc)


def _confirm_or_bad(raw: dict) -> ConfirmRequest:
    try:
        req = ConfirmRequest.model_validate(raw)
    except ValidationError:
        raise _bad_request()
    if not req.confirm:
        raise _bad_request("invalid_request")
    return req


@router.post("/system/shutdown")
async def shutdown(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    _confirm_or_bad(parse_plaintext_json(opened.plaintext))
    log.warning("shutdown requested by client_id=%s", opened.client.client_id)
    asyncio.create_task(
        _delayed_system_action(["systemctl", "poweroff"], _SHUTDOWN_GRACE_SECONDS)
    )
    return seal_response(
        state=state,
        request=request,
        opened=opened,
        body={"ok": True, "shutdown_in_seconds": _SHUTDOWN_GRACE_SECONDS},
    )


@router.post("/system/reboot")
async def reboot(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    _confirm_or_bad(parse_plaintext_json(opened.plaintext))
    log.warning("reboot requested by client_id=%s", opened.client.client_id)
    asyncio.create_task(
        _delayed_system_action(["systemctl", "reboot"], _SHUTDOWN_GRACE_SECONDS)
    )
    return seal_response(
        state=state,
        request=request,
        opened=opened,
        body={"ok": True, "reboot_in_seconds": _SHUTDOWN_GRACE_SECONDS},
    )


# ---------------------------------------------------------------------------
# Pairing reset
# ---------------------------------------------------------------------------


@router.post("/pairing/reset")
async def pairing_reset(request: Request) -> Any:
    state = get_state(request)
    opened = await open_secure_envelope(request)
    _confirm_or_bad(parse_plaintext_json(opened.plaintext))

    response = seal_response(
        state=state, request=request, opened=opened, body={"ok": True}
    )
    # Reset AFTER the response is built — once reset() runs, the calling
    # client's session is invalidated and we couldn't seal a reply.
    state.pairing.reset()
    state.pairing.start()
    state.current_page = "pairing"
    state.force_refresh = True
    log.warning("pairing reset by client_id=%s", opened.client.client_id)
    return response


__all__ = ["router"]
