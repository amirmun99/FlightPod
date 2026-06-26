"""Wipe all FlightPaper pairing state on the local device.

Removes ``paired_clients.json`` and ``pairing_state.json`` so the next
boot lands on the pairing page with a fresh QR.

Note: ``device_identity.json`` is preserved unless you pass ``--rotate``.
Rotating the device identity invalidates any cached pairing on the
phone side too.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running without `pip install -e .` from the repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flightpaper.security.device_identity import (  # noqa: E402
    create_identity,
    load_or_create_identity,
)
from flightpaper.security.key_store import KeyStore  # noqa: E402
from flightpaper.security.pairing import PairingManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset FlightPaper pairing state")
    parser.add_argument(
        "--secure-dir",
        type=Path,
        default=Path.home() / ".flightpaper" / "secure",
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Also rotate the device identity (X25519 keypair + device_id).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation.",
    )
    args = parser.parse_args()

    if not args.yes:
        print(f"This will wipe all pairing state under: {args.secure_dir}")
        if args.rotate:
            print("AND rotate the device identity (forces every paired client to re-pair).")
        try:
            confirm = input("Type 'reset' to continue: ").strip().lower()
        except EOFError:
            confirm = ""
        if confirm != "reset":
            print("Aborted.")
            return 1

    identity = (
        create_identity(args.secure_dir)
        if args.rotate
        else load_or_create_identity(args.secure_dir)
    )
    store = KeyStore(args.secure_dir)
    pairing = PairingManager(
        secure_dir=args.secure_dir,
        identity=identity,
        key_store=store,
    )
    pairing.reset()

    print(f"Reset complete. device_id={identity.device_id}")
    if args.rotate:
        print("Identity rotated; the phone will need to re-pair from a new QR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
