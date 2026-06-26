"""Read battery state via the configured provider (PiSugar 3 by default).

Useful for sanity-checking that ``pisugar-server`` is reachable on the Pi
before running the full FlightPaper service.

Usage:
    python apps/pi/scripts/test_battery.py
    python apps/pi/scripts/test_battery.py --host 127.0.0.1 --port 8423
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without `pip install -e .` from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flightpaper.hardware.battery import (  # noqa: E402
    PiSugar3BatteryProvider,
)
from flightpaper.hardware.pisugar3 import PiSugar3Client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="PiSugar 3 smoke test")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8423)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args()

    client = PiSugar3Client(host=args.host, port=args.port, timeout=args.timeout)
    provider = PiSugar3BatteryProvider(client)

    status = provider.read()
    print(f"percent:        {status.percent}")
    print(f"charging:       {status.charging}")
    print(f"external_power: {status.external_power}")
    print(f"available:      {status.available}")
    return 0 if status.available else 1


if __name__ == "__main__":
    sys.exit(main())
