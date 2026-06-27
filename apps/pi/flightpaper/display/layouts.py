"""Per-page rendering for the Waveshare 2.13" (250x122) ePaper.

Each page is a free function ``render_<name>(draw, image, state)`` that
draws onto a pre-allocated 1-bit Pillow image. The :func:`render_page`
dispatcher in :mod:`renderer` looks them up by name.

Layouts target a tight 250x122 footprint. The first 12 pixels are
reserved for the status bar (shared across pages that opt in).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..opensky.models import Aircraft
from ..utils.geo import cardinal_direction, project_aircraft_to_screen
from ..utils.time_utils import age_seconds, format_age, now_ts
from ..utils.units import meters_to_feet, mps_to_knots
from . import symbols
from .fonts import label_font, status_font, title_font, value_font

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage
    from PIL.ImageDraw import ImageDraw

    from ..api.app_state import AppState

log = logging.getLogger(__name__)


SCREEN_WIDTH = 250
SCREEN_HEIGHT = 122
STATUS_BAR_HEIGHT = 12


# ---------------------------------------------------------------------------
# Status bar (shared across radar/closest/list/status)
# ---------------------------------------------------------------------------


def _draw_status_bar(draw: "ImageDraw", state: "AppState") -> None:
    """Render the top status bar with battery, wifi, api age, location age."""

    font = status_font()
    x = 1
    y = 1

    # Battery icon + percent.
    battery_percent = None  # Phase 6 wires PiSugar in; for now read from state.
    battery_charging = False
    if hasattr(state, "battery_status") and state.battery_status is not None:  # type: ignore[attr-defined]
        battery_percent = state.battery_status.percent  # type: ignore[attr-defined]
        battery_charging = bool(state.battery_status.charging)  # type: ignore[attr-defined]
    symbols.battery_icon(
        draw, top_left=(x, y + 1), percent=battery_percent, charging=battery_charging
    )
    x += 22
    pct_text = f"{battery_percent}%" if battery_percent is not None else "--"
    draw.text((x, y), pct_text, font=font, fill=symbols.BLACK)
    x += 28

    # Wi-Fi marker.
    wifi_connected = bool(state.primary_ip) and state.primary_ip != "0.0.0.0"
    symbols.wifi_icon(draw, top_left=(x, y), connected=wifi_connected, size_px=4)
    x += 16

    # API age.
    api_age = state.opensky_provider.status.last_update_age_seconds
    draw.text((x, y), f"API {format_age(api_age)}", font=font, fill=symbols.BLACK)
    x += 50

    # Location age.
    loc_age = state.location.age_seconds()
    draw.text((x, y), f"LOC {format_age(loc_age)}", font=font, fill=symbols.BLACK)

    # Divider line at the bottom of the bar.
    draw.line(
        (0, STATUS_BAR_HEIGHT, SCREEN_WIDTH, STATUS_BAR_HEIGHT),
        fill=symbols.BLACK,
    )


# ---------------------------------------------------------------------------
# Boot page
# ---------------------------------------------------------------------------


def render_boot(draw: "ImageDraw", image: "PILImage", state: "AppState") -> None:
    title = title_font()
    label = label_font()
    draw.text((10, 26), state.config.app.name, font=title, fill=symbols.BLACK)
    draw.text(
        (10, 56),
        f"v{state.config.app.version}",
        font=label,
        fill=symbols.BLACK,
    )
    draw.text((10, 76), state.identity.device_id, font=label, fill=symbols.BLACK)
    draw.text((10, 96), "Booting...", font=label, fill=symbols.BLACK)


# ---------------------------------------------------------------------------
# Pairing page
# ---------------------------------------------------------------------------


def render_pairing(draw: "ImageDraw", image: "PILImage", state: "AppState") -> None:
    from .qr import QrRenderError, render_pairing_qr  # local import to avoid cycle

    label = label_font()
    status = status_font()

    # No page title — the 250x122 panel can't spare the rows. The QR fills
    # the left of the panel; pairing details sit in a column to its right.
    qr_left = 4
    qr_top = 5
    # Clamp so the QR can never run off the bottom of the panel.
    qr_size = min(112, image.height - 2 * qr_top)

    try:
        uri = state.pairing.qr_uri()
        qr_img = render_pairing_qr(uri, target_px=qr_size)
        image.paste(qr_img, (qr_left, qr_top))
        payload = state.pairing.qr_payload()
        host_text = f"IP: {payload['host']}"
        code_text = f"Code: {payload['code']}"
        ttl = max(0, payload["expires_at"] - now_ts())
        ttl_text = f"Expires: {ttl}s"
    except (QrRenderError, Exception) as exc:  # noqa: BLE001
        log.warning("pairing render fallback (%s)", exc)
        host_text = f"IP: {state.primary_ip}"
        code_text = "Code: --"
        ttl_text = "Open app"
        # Placeholder square where the QR would go.
        draw.rectangle(
            (qr_left, qr_top, qr_left + qr_size, qr_top + qr_size),
            outline=symbols.BLACK,
        )

    right_x = qr_left + qr_size + 10
    draw.text((right_x, 8), "Scan in app", font=label, fill=symbols.BLACK)
    draw.text((right_x, 34), host_text, font=status, fill=symbols.BLACK)
    draw.text((right_x, 60), code_text, font=status, fill=symbols.BLACK)
    draw.text((right_x, 86), ttl_text, font=status, fill=symbols.BLACK)


# ---------------------------------------------------------------------------
# Radar page
# ---------------------------------------------------------------------------


def render_radar(draw: "ImageDraw", image: "PILImage", state: "AppState") -> None:
    _draw_status_bar(draw, state)

    radius_px = 38
    center = (radius_px + 12, STATUS_BAR_HEIGHT + radius_px + 14)
    symbols.radar_ring(draw, center=center, radius=radius_px)
    for cardinal in (0.0, 90.0, 180.0, 270.0):
        symbols.cardinal_tick(draw, center=center, radius=radius_px, bearing_deg=cardinal)

    selected_radius_km = float(state.config.ui.radius_km)
    drawn = 0
    max_drawn = int(state.config.display.max_aircraft_drawn)
    # On-radar callsign labels are intentionally omitted on this 250x122
    # display — the right-hand panel labels the closest target, and free-
    # floating labels collide with each other on a dense scene.
    closest: Aircraft | None = None

    for ac in state.last_aircraft:
        if ac.distance_km is None or ac.bearing_deg is None:
            continue
        point = project_aircraft_to_screen(
            bearing=ac.bearing_deg,
            distance_km=ac.distance_km,
            selected_radius_km=selected_radius_km,
            center_x=center[0],
            center_y=center[1],
            radius_px=radius_px,
        )
        symbols.aircraft_triangle(
            draw, center=(point.x, point.y), heading_deg=ac.true_track_deg, size_px=4
        )
        if closest is None:
            closest = ac
        drawn += 1
        if drawn >= max_drawn:
            break

    # Right-side panel
    right_x = 2 * radius_px + 24
    label = label_font()
    status = status_font()
    draw.text(
        (right_x, STATUS_BAR_HEIGHT + 4),
        f"R {int(selected_radius_km)}km",
        font=label,
        fill=symbols.BLACK,
    )
    if closest is not None:
        draw.text(
            (right_x, STATUS_BAR_HEIGHT + 22),
            "CLOSEST",
            font=status,
            fill=symbols.BLACK,
        )
        draw.text(
            (right_x, STATUS_BAR_HEIGHT + 36),
            closest.callsign or closest.icao24,
            font=label,
            fill=symbols.BLACK,
        )
        if closest.distance_km is not None and closest.bearing_deg is not None:
            draw.text(
                (right_x, STATUS_BAR_HEIGHT + 52),
                f"{closest.distance_km:.1f}km {cardinal_direction(closest.bearing_deg)}",
                font=status,
                fill=symbols.BLACK,
            )
        alt_ft = meters_to_feet(closest.baro_altitude_m)
        if alt_ft is not None:
            draw.text(
                (right_x, STATUS_BAR_HEIGHT + 66),
                f"{int(round(alt_ft))} ft",
                font=status,
                fill=symbols.BLACK,
            )
        if closest.age_seconds is not None:
            draw.text(
                (right_x, STATUS_BAR_HEIGHT + 80),
                f"{closest.age_seconds}s ago",
                font=status,
                fill=symbols.BLACK,
            )
    else:
        draw.text(
            (right_x, STATUS_BAR_HEIGHT + 24),
            "NO TRAFFIC",
            font=label,
            fill=symbols.BLACK,
        )


# ---------------------------------------------------------------------------
# Closest / overhead page
# ---------------------------------------------------------------------------


def render_closest(draw: "ImageDraw", image: "PILImage", state: "AppState") -> None:
    _draw_status_bar(draw, state)

    title = title_font()
    label = label_font()
    status = status_font()

    if not state.last_aircraft:
        draw.text((8, STATUS_BAR_HEIGHT + 6), "NO AIRCRAFT", font=title, fill=symbols.BLACK)
        draw.text(
            (8, STATUS_BAR_HEIGHT + 36),
            f"within {int(state.config.ui.radius_km)} km",
            font=label,
            fill=symbols.BLACK,
        )
        api_age = state.opensky_provider.status.last_update_age_seconds
        draw.text(
            (8, STATUS_BAR_HEIGHT + 60),
            f"Updated {format_age(api_age)}",
            font=status,
            fill=symbols.BLACK,
        )
        return

    overhead_threshold = float(state.config.ui.overhead_threshold_km)
    closest = state.last_aircraft[0]
    is_overhead = (
        closest.distance_km is not None and closest.distance_km <= overhead_threshold
    )
    header = "OVERHEAD" if is_overhead else "CLOSEST"
    draw.text((8, STATUS_BAR_HEIGHT + 2), header, font=title, fill=symbols.BLACK)
    draw.text(
        (8, STATUS_BAR_HEIGHT + 26),
        closest.callsign or closest.icao24,
        font=value_font(),
        fill=symbols.BLACK,
    )

    parts: list[str] = []
    if closest.distance_km is not None and closest.bearing_deg is not None:
        parts.append(
            f"{closest.distance_km:.1f}km {cardinal_direction(closest.bearing_deg)}"
        )
    alt_ft = meters_to_feet(closest.baro_altitude_m)
    if alt_ft is not None:
        parts.append(f"{int(round(alt_ft))} ft")
    if parts:
        draw.text((8, STATUS_BAR_HEIGHT + 56), "  ".join(parts), font=label, fill=symbols.BLACK)

    parts2: list[str] = []
    kt = mps_to_knots(closest.velocity_mps)
    if kt is not None:
        parts2.append(f"{int(round(kt))} kt")
    if closest.true_track_deg is not None:
        parts2.append(f"TRK {int(round(closest.true_track_deg)):03d}°")
    if parts2:
        draw.text((8, STATUS_BAR_HEIGHT + 76), "  ".join(parts2), font=label, fill=symbols.BLACK)
    if closest.age_seconds is not None:
        draw.text(
            (8, STATUS_BAR_HEIGHT + 96),
            f"Seen {closest.age_seconds}s ago",
            font=status,
            fill=symbols.BLACK,
        )


# ---------------------------------------------------------------------------
# Aircraft list page
# ---------------------------------------------------------------------------


def render_list(draw: "ImageDraw", image: "PILImage", state: "AppState") -> None:
    _draw_status_bar(draw, state)

    label = label_font()
    status = status_font()

    draw.text(
        (4, STATUS_BAR_HEIGHT + 1),
        f"NEARBY {int(state.config.ui.radius_km)}km",
        font=label,
        fill=symbols.BLACK,
    )

    # 5 rows leaves clearance for the footer line at SCREEN_HEIGHT - 11.
    rows = state.last_aircraft[:5]
    row_y = STATUS_BAR_HEIGHT + 16
    row_h = 14

    if not rows:
        draw.text((6, row_y + 8), "no traffic visible", font=label, fill=symbols.BLACK)
        return

    for ac in rows:
        cs = (ac.callsign or ac.icao24)[:8]
        dist = f"{ac.distance_km:>5.1f}km" if ac.distance_km is not None else " --  km"
        alt_ft = meters_to_feet(ac.baro_altitude_m)
        alt_text = f"{int(round(alt_ft))}ft" if alt_ft is not None else "--ft"
        # Three columns: callsign | distance | altitude.
        draw.text((4, row_y), cs, font=label, fill=symbols.BLACK)
        draw.text((75, row_y), dist, font=label, fill=symbols.BLACK)
        draw.text((150, row_y), alt_text, font=label, fill=symbols.BLACK)
        row_y += row_h

    # Footer with count + as-of.
    footer_y = SCREEN_HEIGHT - 11
    api_age = state.opensky_provider.status.last_update_age_seconds
    draw.text(
        (4, footer_y),
        f"{len(state.last_aircraft)} total  upd {format_age(api_age)}",
        font=status,
        fill=symbols.BLACK,
    )


# ---------------------------------------------------------------------------
# Status page
# ---------------------------------------------------------------------------


def render_status(draw: "ImageDraw", image: "PILImage", state: "AppState") -> None:
    _draw_status_bar(draw, state)

    label = label_font()
    status_f = status_font()

    draw.text((4, STATUS_BAR_HEIGHT + 1), "STATUS", font=label, fill=symbols.BLACK)

    pair_state = "paired" if state.pairing.is_paired() else "unpaired"
    api_status = state.opensky_provider.status
    aircraft_count = api_status.aircraft_count
    api_label = "OK" if api_status.last_status == "ok" else api_status.last_status.upper()

    rows = [
        f"App:  {pair_state}",
        f"Net:  {state.primary_ip}",
        f"Loc:  {state.location.status_dict()['source'] or '--'}",
        f"API:  {api_label}  AC {aircraft_count}",
        f"Page: {state.current_page}",
    ]

    y = STATUS_BAR_HEIGHT + 16
    for row in rows:
        draw.text((4, y), row, font=status_f, fill=symbols.BLACK)
        y += 14


# ---------------------------------------------------------------------------
# Error page
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorScreen:
    title: str
    detail: tuple[str, ...]


_ERROR_TEMPLATES: dict[str, ErrorScreen] = {
    "no_wifi": ErrorScreen("NO WIFI", ("Connect hotspot", "or check saved SSID")),
    "no_internet": ErrorScreen("NO INTERNET", ("Wi-Fi up but unreachable", "")),
    "no_pairing": ErrorScreen("PAIR DEVICE", ("Scan QR in app",)),
    "no_location": ErrorScreen("NO LOCATION", ("Open app", "Start Live GPS")),
    "api_error": ErrorScreen("API ERROR", ("Showing cached", "Retry later")),
    "api_limited": ErrorScreen("API LIMITED", ("Showing cached", "Retry later")),
    "low_battery": ErrorScreen("LOW BATTERY", ("Battery saver on",)),
    "critical_battery": ErrorScreen("CRITICAL BAT", ("Shutting down",)),
    "render_error": ErrorScreen("RENDER ERROR", ("see logs",)),
}


def render_error(
    draw: "ImageDraw",
    image: "PILImage",
    state: "AppState",
    *,
    kind: str = "render_error",
    detail_override: tuple[str, ...] | None = None,
) -> None:
    template = _ERROR_TEMPLATES.get(kind, _ERROR_TEMPLATES["render_error"])
    title = title_font()
    label = label_font()
    draw.text((10, 20), template.title, font=title, fill=symbols.BLACK)
    lines = detail_override if detail_override is not None else template.detail
    for i, line in enumerate(lines):
        draw.text((10, 56 + i * 18), line, font=label, fill=symbols.BLACK)
    # Always include IP at the bottom so the operator can SSH in.
    draw.text(
        (10, SCREEN_HEIGHT - 14),
        f"IP {state.primary_ip}",
        font=status_font(),
        fill=symbols.BLACK,
    )


# ---------------------------------------------------------------------------
# Shutdown confirmation
# ---------------------------------------------------------------------------


def render_shutdown_confirm(
    draw: "ImageDraw", image: "PILImage", state: "AppState"
) -> None:
    title = title_font()
    label = label_font()
    draw.text((10, 24), "SHUTDOWN?", font=title, fill=symbols.BLACK)
    draw.text((10, 56), "Hold button to confirm.", font=label, fill=symbols.BLACK)
    draw.text((10, 76), "Release to cancel.", font=label, fill=symbols.BLACK)
    draw.text(
        (10, SCREEN_HEIGHT - 14),
        f"uptime {age_seconds(int(state.started_at), now=now_ts())}s",
        font=status_font(),
        fill=symbols.BLACK,
    )


__all__ = [
    "SCREEN_HEIGHT",
    "SCREEN_WIDTH",
    "STATUS_BAR_HEIGHT",
    "render_boot",
    "render_closest",
    "render_error",
    "render_list",
    "render_pairing",
    "render_radar",
    "render_shutdown_confirm",
    "render_status",
]
