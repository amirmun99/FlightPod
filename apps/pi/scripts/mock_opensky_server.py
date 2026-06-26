"""Mock OpenSky Network server for FlightPaper development.

Run standalone:

    python apps/pi/scripts/mock_opensky_server.py --port 9090

Then point the FlightPaper config at it:

    opensky:
      base_url: "http://127.0.0.1:9090"

Or, in tests, import :data:`app` and wrap it in
``httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`` /
``httpx.MockTransport`` to avoid spinning up uvicorn.

The scenario is controlled by an ``X-Scenario`` request header or a
``scenario`` query parameter. Supported scenarios are listed in
:data:`SCENARIOS`.
"""

from __future__ import annotations

import argparse
import time
from typing import Any

from fastapi import FastAPI, Header, Query, Request, Response

app = FastAPI(title="FlightPaper Mock OpenSky", version="0.1.0")


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------
#
# Each builder takes (now_ts, center_lat, center_lon) and returns the JSON
# body OpenSky would normally return. Center lat/lon come from the bbox.


def _now() -> int:
    return int(time.time())


def _state(
    *,
    icao24: str,
    callsign: str | None,
    country: str | None,
    lat: float | None,
    lon: float | None,
    baro_m: float | None,
    geo_m: float | None,
    velocity_mps: float | None,
    track_deg: float | None,
    on_ground: bool,
    last_contact_offset_s: int = 0,
    now_ts: int | None = None,
) -> list[Any]:
    t = now_ts if now_ts is not None else _now()
    contact = t - last_contact_offset_s
    return [
        icao24,
        callsign.ljust(8) if callsign else None,
        country,
        contact if lat is not None else None,
        contact,
        lon,
        lat,
        baro_m,
        on_ground,
        velocity_mps,
        track_deg,
        0.0,            # vertical rate
        None,           # sensors
        geo_m,
        "1234",         # squawk
        False,          # spi
        0,              # position source
    ]


def _scenario_none(_lat: float, _lon: float) -> dict[str, Any]:
    return {"time": _now(), "states": []}


def _scenario_one_overhead(lat: float, lon: float) -> dict[str, Any]:
    states = [
        _state(
            icao24="ac0001",
            callsign="ACA123",
            country="Canada",
            lat=lat + 0.005,
            lon=lon + 0.005,
            baro_m=9525.0,
            geo_m=9540.0,
            velocity_mps=240.0,
            track_deg=82.0,
            on_ground=False,
        )
    ]
    return {"time": _now(), "states": states}


def _scenario_many(lat: float, lon: float) -> dict[str, Any]:
    now = _now()
    grid = [
        # (icao, callsign, dlat, dlon, alt_m, vel_mps, trk, last_contact_offset)
        ("ac0001", "ACA123", 0.005, 0.005, 9525, 240, 82, 8),
        ("ac0002", "WJA456", 0.05, -0.04, 8550, 230, 270, 12),
        ("ac0003", "DAL089", 0.07, 0.10, 10400, 250, 30, 5),
        ("ac0004", "UAL022", 0.15, -0.15, 3600, 180, 350, 20),
        ("ac0005", "AAL700", -0.03, 0.02, 11000, 245, 200, 9),
        ("ac0006", "JBU100", -0.10, 0.10, 7500, 220, 110, 18),
        ("ac0007", "FDX300", 0.20, 0.20, 12000, 260, 60, 25),
    ]
    states = [
        _state(
            icao24=icao,
            callsign=cs,
            country="USA",
            lat=lat + dlat,
            lon=lon + dlon,
            baro_m=float(alt),
            geo_m=float(alt + 30),
            velocity_mps=float(vel),
            track_deg=float(trk),
            on_ground=False,
            last_contact_offset_s=off,
            now_ts=now,
        )
        for icao, cs, dlat, dlon, alt, vel, trk, off in grid
    ]
    return {"time": now, "states": states}


def _scenario_missing_fields(lat: float, lon: float) -> dict[str, Any]:
    states = [
        # Missing callsign, baro altitude, velocity.
        _state(
            icao24="ac0010",
            callsign=None,
            country=None,
            lat=lat + 0.02,
            lon=lon - 0.02,
            baro_m=None,
            geo_m=8000.0,
            velocity_mps=None,
            track_deg=None,
            on_ground=False,
        ),
        # Missing lat/lon (no position fix).
        _state(
            icao24="ac0011",
            callsign="GHOST1",
            country="USA",
            lat=None,
            lon=None,
            baro_m=10000.0,
            geo_m=10000.0,
            velocity_mps=220.0,
            track_deg=180.0,
            on_ground=False,
        ),
    ]
    return {"time": _now(), "states": states}


def _scenario_stale(lat: float, lon: float) -> dict[str, Any]:
    return {
        "time": _now(),
        "states": [
            _state(
                icao24="ac0020",
                callsign="STALE1",
                country="USA",
                lat=lat + 0.03,
                lon=lon + 0.03,
                baro_m=11000.0,
                geo_m=11000.0,
                velocity_mps=200.0,
                track_deg=270.0,
                on_ground=False,
                last_contact_offset_s=600,  # 10 minutes old
            )
        ],
    }


def _scenario_ground(lat: float, lon: float) -> dict[str, Any]:
    return {
        "time": _now(),
        "states": [
            _state(
                icao24="ac0030",
                callsign="TAXI1",
                country="USA",
                lat=lat + 0.001,
                lon=lon + 0.001,
                baro_m=200.0,
                geo_m=200.0,
                velocity_mps=10.0,
                track_deg=90.0,
                on_ground=True,
            )
        ],
    }


SCENARIOS = {
    "none": _scenario_none,
    "one_overhead": _scenario_one_overhead,
    "many": _scenario_many,
    "missing_fields": _scenario_missing_fields,
    "stale": _scenario_stale,
    "ground": _scenario_ground,
    "rate_limit": None,  # handled specially in the route
    "error": None,       # handled specially in the route
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/states/all")
def get_states_all(
    request: Request,
    lamin: float = Query(...),
    lomin: float = Query(...),
    lamax: float = Query(...),
    lomax: float = Query(...),
    extended: int | None = Query(default=None),
    scenario: str | None = Query(default=None),
    x_scenario: str | None = Header(default=None, alias="X-Scenario"),
) -> Response:
    chosen = (scenario or x_scenario or "many").lower()
    if chosen == "rate_limit":
        return Response(
            content='{"detail":"rate limited"}',
            status_code=429,
            headers={"Retry-After": "30", "X-Rate-Limit-Remaining": "0"},
            media_type="application/json",
        )
    if chosen == "error":
        return Response(status_code=500, content='{"detail":"boom"}', media_type="application/json")

    builder = SCENARIOS.get(chosen)
    if builder is None:
        return Response(status_code=400, content=f'{{"detail":"unknown scenario: {chosen}"}}')

    center_lat = (lamin + lamax) / 2
    center_lon = (lomin + lomax) / 2

    body = builder(center_lat, center_lon)
    headers = {"X-Rate-Limit-Remaining": "999"}
    return Response(
        content=__import__("json").dumps(body),
        status_code=200,
        headers=headers,
        media_type="application/json",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "mock-opensky"}


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="FlightPaper mock OpenSky server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9090)
    args = parser.parse_args()

    import uvicorn  # local import so the module imports cheaply

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
