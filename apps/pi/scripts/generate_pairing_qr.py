"""Render a sample pairing QR + payload to disk.

Useful for dev iteration before the ePaper hardware is wired. Defaults
write into the OS temp directory; pass ``--out`` to redirect.

Usage:
    python apps/pi/scripts/generate_pairing_qr.py
    python apps/pi/scripts/generate_pairing_qr.py --out /tmp/pair.png --host 172.20.10.4
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Allow running without `pip install -e .` from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flightpaper.display.qr import render_pairing_qr  # noqa: E402
from flightpaper.security.device_identity import (  # noqa: E402
    load_or_create_identity,
)
from flightpaper.security.key_store import KeyStore  # noqa: E402
from flightpaper.security.pairing import PairingManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a sample pairing QR")
    parser.add_argument(
        "--secure-dir",
        type=Path,
        default=Path.home() / ".flightpaper" / "secure",
        help="Directory where identity / key store / pairing state live.",
    )
    parser.add_argument("--device-name", default="FlightPaper Dev")
    parser.add_argument("--host", default="172.20.10.4")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--expires-seconds", type=int, default=600)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(tempfile.gettempdir()) / "flightpaper_pairing_qr.png",
    )
    args = parser.parse_args()

    args.secure_dir.mkdir(parents=True, exist_ok=True)
    identity = load_or_create_identity(args.secure_dir, device_name=args.device_name)

    store = KeyStore(args.secure_dir)
    manager = PairingManager(
        secure_dir=args.secure_dir,
        identity=identity,
        key_store=store,
        host_provider=lambda: (args.host, args.port),
        expires_seconds=args.expires_seconds,
    )
    state = manager.start()
    payload = manager.qr_payload()
    uri = manager.qr_uri()

    print(json.dumps(payload, indent=2))
    print()
    print(f"URI: {uri}")
    print(f"Short code: {payload['code']}")
    print(f"Pairing expires at: {state.expires_at}")

    img = render_pairing_qr(uri)
    img.save(args.out)
    print(f"\nQR image saved to: {args.out}  (size {img.size[0]}x{img.size[1]})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
