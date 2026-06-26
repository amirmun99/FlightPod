"""Smoke-test the OpenSky pipeline against the mock server (or a real
OpenSky base URL if you point at one).

Examples:

    # Against the bundled mock (no network)
    python apps/pi/scripts/mock_opensky_server.py --port 9090 &
    python apps/pi/scripts/test_opensky.py --base-url http://127.0.0.1:9090 \\
        --scenario many --lat 43.3255 --lon -79.7990

    # Against the real OpenSky API (anonymous mode)
    python apps/pi/scripts/test_opensky.py \\
        --base-url https://opensky-network.org/api \\
        --lat 43.3255 --lon -79.7990 --radius 25
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without `pip install -e .` from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flightpaper.aircraft.filters import FilterConfig  # noqa: E402
from flightpaper.aircraft.processor import UserPosition, process_states  # noqa: E402
from flightpaper.opensky.client import OpenSkyClient  # noqa: E402
from flightpaper.opensky.provider import OpenSkyProvider  # noqa: E402
from flightpaper.opensky.rate_limit import RateLimiter  # noqa: E402
from flightpaper.utils.geo import latlon_bbox  # noqa: E402
from flightpaper.utils.time_utils import now_ts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenSky pipeline smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:9090")
    parser.add_argument("--lat", type=float, default=43.3255)
    parser.add_argument("--lon", type=float, default=-79.7990)
    parser.add_argument("--radius", type=float, default=25.0)
    parser.add_argument("--scenario", default="many")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    bbox = latlon_bbox(args.lat, args.lon, args.radius)
    print(
        f"bbox: lamin={bbox.lamin:.4f} lomin={bbox.lomin:.4f} "
        f"lamax={bbox.lamax:.4f} lomax={bbox.lomax:.4f}"
    )

    client = OpenSkyClient(
        base_url=args.base_url,
        timeout_s=8.0,
        user_agent="FlightPaper-smoke/0.1.0",
    )
    # Inject the scenario header into every request to the mock.
    client._http.headers["X-Scenario"] = args.scenario  # noqa: SLF001 - dev convenience

    limiter = RateLimiter(min_interval_s=0.0)
    provider = OpenSkyProvider(client=client, limiter=limiter)

    states = provider.fetch(bbox=bbox)
    print(f"raw states: {states.count} aircraft, time={states.time}")

    user = UserPosition(lat=args.lat, lon=args.lon)
    cfg = FilterConfig(
        include_ground_aircraft=False,
        max_age_seconds=120,
        radius_km=args.radius,
    )
    enriched = process_states(states, user=user, config=cfg, now_ts=now_ts())
    print(f"after filter/enrich/sort: {len(enriched)} aircraft within {args.radius} km")
    for ac in enriched[: args.limit]:
        print(
            f"  {ac.icao24} {ac.callsign or '------':6s} "
            f"d={ac.distance_km:5.1f}km b={ac.bearing_deg:5.1f}° "
            f"alt_m={ac.baro_altitude_m} vel_mps={ac.velocity_mps} age={ac.age_seconds}s"
        )

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
