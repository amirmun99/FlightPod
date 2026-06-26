"""Tests for /api/secure/* — every endpoint exercised end-to-end."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from flightpaper.api.app_state import AppState
from flightpaper.opensky.models import Aircraft

from .conftest import (
    PairedSession,
    open_response_envelope,
    perform_pairing,
    send_secure,
)


def _now() -> int:
    """Real wall-clock seconds. The server checks the envelope ts against
    its own ``now_ts()``, so tests must use a recent timestamp."""

    return int(time.time())


# ---------------------------------------------------------------------------
# Pairing fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def session(client: TestClient, app_state: AppState) -> PairedSession:
    return perform_pairing(client, state=app_state)


# ---------------------------------------------------------------------------
# Auth rejection
# ---------------------------------------------------------------------------


def test_secure_route_rejects_missing_envelope(client: TestClient) -> None:
    # GET still requires a body; without one we should get an envelope error.
    resp = client.get("/api/secure/status")
    assert resp.status_code in (400, 401, 405)


def test_secure_route_rejects_bare_json(client: TestClient) -> None:
    resp = client.post("/api/secure/location", json={"hello": "world"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "bad_envelope"


def test_secure_route_rejects_unknown_client(client: TestClient, app_state: AppState) -> None:
    # Build an envelope with a non-paired client_id but otherwise valid shape.
    from flightpaper.security import crypto

    fake_key = b"\x00" * 32
    from flightpaper.api.secure_envelope import seal_envelope

    env = seal_envelope(
        payload={"x": 1},
        key=fake_key,
        method="GET",
        path="/api/secure/status",
        device_id=app_state.identity.device_id,
        client_id="iphone_aaaaaaaaaaaa",
        key_id="main",
        seq=1,
        ts=1_700_000_000,
    )
    resp = client.request("GET", "/api/secure/status", json=env)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "not_paired"


# ---------------------------------------------------------------------------
# /location
# ---------------------------------------------------------------------------


def test_post_location_round_trip(
    client: TestClient, app_state: AppState, session: PairedSession
) -> None:
    now = _now()
    body = {
        "lat": 43.3255,
        "lon": -79.7990,
        "accuracy_m": 8.5,
        "altitude_m": 120.0,
        "heading_deg": 52.0,
        "speed_mps": 1.4,
        "timestamp": now,
        "source": "iphone_background",
    }
    resp = send_secure(
        client, session=session, method="POST", path="/api/secure/location",
        body=body, seq=1, ts=now,
    )
    assert resp.status_code == 200
    payload = open_response_envelope(
        session=session, envelope=resp.json(), path="/api/secure/location"
    )
    assert payload["accepted"] is True
    # Manager state mutated.
    loc = app_state.location.current()
    assert loc is not None and loc.lat == 43.3255


def test_post_location_rejects_bad_payload(
    client: TestClient, session: PairedSession
) -> None:
    resp = send_secure(
        client, session=session, method="POST", path="/api/secure/location",
        body={"lat": 999, "lon": 0, "timestamp": _now(), "source": "iphone_background"},
        seq=1, ts=_now(),
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_request"


def test_replay_rejected(
    client: TestClient, app_state: AppState, session: PairedSession
) -> None:
    body = {
        "lat": 0.0,
        "lon": 0.0,
        "timestamp": _now(),
        "source": "iphone_foreground",
    }
    resp1 = send_secure(
        client, session=session, method="POST", path="/api/secure/location",
        body=body, seq=1, ts=_now(),
    )
    assert resp1.status_code == 200
    # Resend with same seq.
    resp2 = send_secure(
        client, session=session, method="POST", path="/api/secure/location",
        body=body, seq=1, ts=_now(),
    )
    assert resp2.status_code == 401
    assert resp2.json()["error"]["code"] == "replay"


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------


def test_status_round_trip(
    client: TestClient, app_state: AppState, session: PairedSession
) -> None:
    # Stamp a fresh location so the status reflects "fresh".
    now = _now()
    body = {
        "lat": 43.3255, "lon": -79.7990, "timestamp": now, "source": "iphone_background",
    }
    send_secure(
        client, session=session, method="POST", path="/api/secure/location",
        body=body, seq=1, ts=now,
    )

    resp = send_secure(
        client, session=session, method="GET", path="/api/secure/status",
        body={}, seq=2, ts=now,
    )
    assert resp.status_code == 200
    payload = open_response_envelope(
        session=session, envelope=resp.json(), path="/api/secure/status"
    )
    assert payload["device"]["id"] == app_state.identity.device_id
    assert payload["location"]["source"] == "iphone_background"
    assert payload["display"]["page"] == app_state.current_page


# ---------------------------------------------------------------------------
# /aircraft
# ---------------------------------------------------------------------------


def test_aircraft_list_uses_cache(
    client: TestClient, app_state: AppState, session: PairedSession
) -> None:
    # Inject one aircraft into the in-memory cache directly.
    app_state.last_aircraft = [
        Aircraft(
            icao24="ac0001",
            callsign="ACA123",
            origin_country="Canada",
            longitude=-79.81,
            latitude=43.33,
            baro_altitude_m=9525.0,
            on_ground=False,
            velocity_mps=240.0,
            true_track_deg=82.0,
            vertical_rate_mps=0.0,
            geo_altitude_m=9540.0,
            distance_km=1.7,
            bearing_deg=51.0,
            age_seconds=8,
        )
    ]

    resp = send_secure(
        client, session=session, method="GET",
        path="/api/secure/aircraft",
        body={}, seq=1, ts=_now(),
    )
    assert resp.status_code == 200
    body = open_response_envelope(
        session=session, envelope=resp.json(), path="/api/secure/aircraft"
    )
    assert body["count"] == 1
    ac = body["aircraft"][0]
    assert ac["callsign"] == "ACA123"
    assert ac["baro_altitude_ft"] == pytest.approx(31250, rel=1e-3)
    assert ac["velocity_kt"] == pytest.approx(467, abs=1)


# ---------------------------------------------------------------------------
# /config
# ---------------------------------------------------------------------------


def test_get_and_patch_config(
    client: TestClient, app_state: AppState, session: PairedSession
) -> None:
    resp = send_secure(
        client, session=session, method="GET", path="/api/secure/config",
        body={}, seq=1, ts=_now(),
    )
    assert resp.status_code == 200
    body = open_response_envelope(
        session=session, envelope=resp.json(), path="/api/secure/config"
    )
    assert body["ui"]["radius_km"] == 25.0

    resp = send_secure(
        client, session=session, method="PATCH", path="/api/secure/config",
        body={"ui_radius_km": 50, "opensky_update_interval_seconds": 30},
        seq=2, ts=_now(),
    )
    assert resp.status_code == 200
    body = open_response_envelope(
        session=session, envelope=resp.json(), path="/api/secure/config"
    )
    assert body["ui"]["radius_km"] == 50
    assert body["opensky"]["update_interval_seconds"] == 30
    # Side effect into the live config object.
    assert app_state.config.ui.radius_km == 50


def test_patch_config_rejects_out_of_range(
    client: TestClient, session: PairedSession
) -> None:
    resp = send_secure(
        client, session=session, method="PATCH", path="/api/secure/config",
        body={"ui_radius_km": -10}, seq=1, ts=_now(),
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /display/page + /refresh
# ---------------------------------------------------------------------------


def test_set_page_succeeds(
    client: TestClient, app_state: AppState, session: PairedSession
) -> None:
    resp = send_secure(
        client, session=session, method="POST", path="/api/secure/display/page",
        body={"page": "list"}, seq=1, ts=_now(),
    )
    assert resp.status_code == 200
    body = open_response_envelope(
        session=session, envelope=resp.json(), path="/api/secure/display/page"
    )
    assert body["page"] == "list"
    assert app_state.current_page == "list"


def test_set_page_rejects_unknown(
    client: TestClient, session: PairedSession
) -> None:
    resp = send_secure(
        client, session=session, method="POST", path="/api/secure/display/page",
        body={"page": "bogus"}, seq=1, ts=_now(),
    )
    assert resp.status_code == 400


def test_refresh_triggers_force_flag(
    client: TestClient, app_state: AppState, session: PairedSession
) -> None:
    app_state.force_refresh = False
    app_state.force_poll = False
    resp = send_secure(
        client, session=session, method="POST", path="/api/secure/refresh",
        body={}, seq=1, ts=_now(),
    )
    assert resp.status_code == 200
    assert app_state.force_refresh is True
    assert app_state.force_poll is True


# ---------------------------------------------------------------------------
# /system/* + /pairing/reset
# ---------------------------------------------------------------------------


def test_shutdown_requires_confirm(
    client: TestClient, session: PairedSession
) -> None:
    resp = send_secure(
        client, session=session, method="POST", path="/api/secure/system/shutdown",
        body={"confirm": False}, seq=1, ts=_now(),
    )
    assert resp.status_code == 400


def test_pairing_reset_invalidates_client(
    client: TestClient, app_state: AppState, session: PairedSession
) -> None:
    resp = send_secure(
        client, session=session, method="POST", path="/api/secure/pairing/reset",
        body={"confirm": True}, seq=1, ts=_now(),
    )
    assert resp.status_code == 200
    # Following request from the same session must now fail (not_paired).
    resp2 = send_secure(
        client, session=session, method="GET", path="/api/secure/status",
        body={}, seq=2, ts=_now(),
    )
    assert resp2.status_code == 401
    assert resp2.json()["error"]["code"] == "not_paired"
    # Pairing window is open again with a fresh secret.
    assert client.get("/api/public/pairing-status").json()["state"] == "pairing_pending"
