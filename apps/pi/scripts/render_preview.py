"""Render any FlightPaper ePaper page to a PNG without hardware.

Builds a synthetic :class:`AppState` populated with a chosen scenario,
calls :func:`render_page`, and writes the resulting 1-bit Pillow image
to disk.

Usage:
    python apps/pi/scripts/render_preview.py --page radar --output /tmp/radar.png
    python apps/pi/scripts/render_preview.py --page radar --scenario many --output /tmp/many.png
    python apps/pi/scripts/render_preview.py --page error --scenario no_wifi --output /tmp/wifi.png
    python apps/pi/scripts/render_preview.py --all --output-dir /tmp/flightpaper-previews/
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

# Allow running without `pip install -e .` from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time  # noqa: E402

import httpx  # noqa: E402

from flightpaper.api.app_state import build_app_state  # noqa: E402
from flightpaper.display.renderer import render_page  # noqa: E402
from flightpaper.hardware.battery import BatteryStatus  # noqa: E402
from flightpaper.opensky.models import Aircraft  # noqa: E402


# Pages directly renderable.
PAGES = ("boot", "pairing", "radar", "closest", "list", "status", "shutdown_confirm")
ERROR_KINDS = (
    "no_wifi",
    "no_internet",
    "no_pairing",
    "no_location",
    "api_error",
    "api_limited",
    "low_battery",
    "critical_battery",
)


def _mock_opensky_handler(scenario: str):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content='{"time": 0, "states": []}')
    _ = scenario  # not exercised; provider is bypassed for preview.
    return handler


def _aircraft_fixture(n: int) -> list[Aircraft]:
    base = [
        ("ac0001", "ACA123", 0.7, 36.0, 9525.0, 240.0, 82.0, 8),
        ("ac0002", "WJA456", 6.4, 329.8, 8550.0, 230.0, 270.0, 12),
        ("ac0003", "DAL089", 11.2, 46.1, 10400.0, 250.0, 30.0, 5),
        ("ac0004", "UAL022", 18.0, 350.0, 3600.0, 180.0, 350.0, 20),
        ("ac0005", "AAL700", 3.7, 154.1, 11000.0, 245.0, 200.0, 9),
        ("ac0006", "JBU100", 13.8, 143.9, 7500.0, 220.0, 110.0, 18),
        ("ac0007", "FDX300", 19.5, 60.0, 12000.0, 260.0, 60.0, 25),
    ]
    out: list[Aircraft] = []
    for icao, cs, dist, bearing, alt_m, vel_mps, track, age in base[:n]:
        out.append(
            Aircraft(
                icao24=icao,
                callsign=cs,
                origin_country="USA",
                longitude=-79.79 + dist / 200,
                latitude=43.33 + dist / 200,
                baro_altitude_m=alt_m,
                geo_altitude_m=alt_m + 30,
                on_ground=False,
                velocity_mps=vel_mps,
                true_track_deg=track,
                vertical_rate_mps=0.0,
                squawk="1234",
                distance_km=dist,
                bearing_deg=bearing,
                age_seconds=age,
                time_position=int(time.time()) - age,
                last_contact=int(time.time()) - age,
            )
        )
    return out


def _apply_scenario(state, scenario: str) -> None:
    now = int(time.time())
    if scenario in ("none", "empty"):
        state.last_aircraft = []
    elif scenario == "one":
        state.last_aircraft = _aircraft_fixture(1)
    elif scenario == "many":
        state.last_aircraft = _aircraft_fixture(7)
    if scenario != "no_location":
        # Plant a synthetic location so the radar can render bbox-relative.
        from flightpaper.location.models import Location, LocationPayload

        payload = LocationPayload(
            lat=43.3255, lon=-79.7990,
            accuracy_m=8.0, altitude_m=120.0,
            heading_deg=52.0, speed_mps=1.4,
            source="iphone_foreground",
            timestamp=now,
        )
        state.location.apply_phone_payload(payload, now=now)

    # Battery
    if scenario == "low_battery":
        state.battery_status = BatteryStatus(percent=12, charging=False, external_power=False)
    elif scenario == "critical_battery":
        state.battery_status = BatteryStatus(percent=3, charging=False, external_power=False)
    else:
        state.battery_status = BatteryStatus(percent=82, charging=False, external_power=False)

    state.opensky_provider.status.last_update_age_seconds = 12
    state.opensky_provider.status.aircraft_count = len(state.last_aircraft)
    state.opensky_provider.status.last_status = "ok"


def _build_state(tmp_dir: Path, scenario: str):
    state = build_app_state(
        secure_dir=tmp_dir / "secure",
        opensky_transport=httpx.MockTransport(_mock_opensky_handler(scenario)),
        host_provider_override="172.20.10.4",
    )
    _apply_scenario(state, scenario)
    return state


def _render_error(state, kind: str):
    """Render an error page with a specific kind override."""

    from PIL import Image, ImageDraw
    from flightpaper.display import layouts

    width = int(state.config.display.width)
    height = int(state.config.display.height)
    image = Image.new("1", (width, height), color=1)
    draw = ImageDraw.Draw(image)
    layouts.render_error(draw, image, state, kind=kind)
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a FlightPaper page to PNG")
    parser.add_argument(
        "--page",
        choices=("error",) + PAGES,
        default=None,
        help="Page to render. Required unless --all is set.",
    )
    parser.add_argument(
        "--scenario",
        choices=("none", "one", "many", "no_location", "low_battery", "critical_battery") + ERROR_KINDS,
        default="many",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Render every page (and every error kind) to --output-dir.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "flightpaper-previews",
    )
    args = parser.parse_args()

    if not args.all and args.page is None:
        parser.error("--page is required unless --all is set")

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp_dir = Path(raw_tmp)
        state = _build_state(tmp_dir, args.scenario)

        if args.all:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for page in PAGES:
                state.current_page = page
                image = render_page(state, page)
                out = args.output_dir / f"{page}.png"
                image.save(out)
                print(f"  {page:20s} -> {out}")
            for kind in ERROR_KINDS:
                state.current_page = "error"
                image = _render_error(state, kind)
                out = args.output_dir / f"error_{kind}.png"
                image.save(out)
                print(f"  error/{kind:14s} -> {out}")
            return 0

        if args.page == "error":
            kind = args.scenario if args.scenario in ERROR_KINDS else "render_error"
            image = _render_error(state, kind)
        else:
            state.current_page = args.page
            image = render_page(state, args.page)

        out = args.output or (Path(tempfile.gettempdir()) / f"flightpaper_{args.page}.png")
        image.save(out)
        print(f"saved {image.size[0]}x{image.size[1]} 1-bit PNG to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
