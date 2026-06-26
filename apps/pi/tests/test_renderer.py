"""Smoke tests for the page renderer.

Each page must render without raising on a representative AppState and
produce a 1-bit Pillow image at the configured display size.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest

from flightpaper.api.app_state import AppState, build_app_state
from flightpaper.display import layouts
from flightpaper.display.renderer import list_pages, render_page
from flightpaper.hardware.battery import BatteryStatus
from flightpaper.location.models import LocationPayload
from flightpaper.opensky.models import Aircraft


def _mock_opensky(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content='{"time": 0, "states": []}')


@pytest.fixture
def populated_state(tmp_path: Path) -> AppState:
    state = build_app_state(
        secure_dir=tmp_path / "secure",
        opensky_transport=httpx.MockTransport(_mock_opensky),
        host_provider_override="172.20.10.4",
    )
    # Plant a real-ish location and aircraft so the radar / list pages
    # have something to draw.
    now = int(time.time())
    state.location.apply_phone_payload(
        LocationPayload(
            lat=43.3255, lon=-79.7990,
            accuracy_m=8.0, altitude_m=120.0,
            heading_deg=52.0, speed_mps=1.4,
            source="iphone_foreground",
            timestamp=now,
        ),
        now=now,
    )
    state.last_aircraft = [
        Aircraft(
            icao24="ac0001",
            callsign="ACA123",
            origin_country="Canada",
            longitude=-79.81, latitude=43.33,
            baro_altitude_m=9525.0, geo_altitude_m=9540.0,
            on_ground=False,
            velocity_mps=240.0, true_track_deg=82.0, vertical_rate_mps=0.0,
            squawk="1234",
            distance_km=1.7, bearing_deg=51.0, age_seconds=8,
            time_position=now - 8, last_contact=now - 8,
        ),
        Aircraft(
            icao24="ac0002",
            callsign="WJA456",
            origin_country="Canada",
            longitude=-79.85, latitude=43.39,
            baro_altitude_m=8550.0, geo_altitude_m=8550.0,
            on_ground=False,
            velocity_mps=230.0, true_track_deg=270.0, vertical_rate_mps=0.0,
            distance_km=6.4, bearing_deg=329.8, age_seconds=12,
            time_position=now - 12, last_contact=now - 12,
        ),
    ]
    state.battery_status = BatteryStatus(percent=82, charging=False, external_power=False)
    state.opensky_provider.status.last_update_age_seconds = 12
    state.opensky_provider.status.aircraft_count = 2
    state.opensky_provider.status.last_status = "ok"
    yield state
    state.opensky_client.close()


@pytest.fixture
def empty_state(tmp_path: Path) -> AppState:
    state = build_app_state(
        secure_dir=tmp_path / "secure",
        opensky_transport=httpx.MockTransport(_mock_opensky),
        host_provider_override="172.20.10.4",
    )
    yield state
    state.opensky_client.close()


# ---------------------------------------------------------------------------
# Each page renders without exception
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("page", list_pages())
def test_every_page_renders(populated_state: AppState, page: str) -> None:
    populated_state.current_page = page
    image = render_page(populated_state)
    assert image.mode == "1"
    assert image.size == (250, 122)


@pytest.mark.parametrize("page", list_pages())
def test_every_page_renders_empty_state(empty_state: AppState, page: str) -> None:
    empty_state.current_page = page
    image = render_page(empty_state)
    assert image.mode == "1"
    assert image.size == (250, 122)


def test_unknown_page_falls_back_to_error(populated_state: AppState) -> None:
    populated_state.current_page = "totally_not_a_page"
    image = render_page(populated_state)
    assert image.size == (250, 122)


def test_error_page_renders_each_kind(populated_state: AppState) -> None:
    from PIL import Image, ImageDraw

    for kind in (
        "no_wifi", "no_internet", "no_pairing", "no_location",
        "api_error", "api_limited", "low_battery", "critical_battery",
    ):
        img = Image.new("1", (250, 122), color=1)
        draw = ImageDraw.Draw(img)
        layouts.render_error(draw, img, populated_state, kind=kind)
        assert img.size == (250, 122)


def test_rotation_swaps_dimensions(populated_state: AppState) -> None:
    populated_state.config.display.rotation = 90
    populated_state.current_page = "status"
    image = render_page(populated_state)
    # 90° rotation swaps width/height (PIL ``expand=True``).
    assert image.size == (122, 250)


def test_pairing_page_includes_qr(populated_state: AppState) -> None:
    # The pairing page reads from the pairing manager; since the test
    # bootstrap auto-opens a pairing window, the QR should fit.
    populated_state.current_page = "pairing"
    image = render_page(populated_state)
    # The rendered image should be non-uniform (i.e. not all white).
    histogram = image.histogram()
    # 1-bit images histogram = [black_count, white_count]
    assert histogram[0] > 100, "pairing page should have black pixels (QR + text)"
