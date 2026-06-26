"""Short human-readable code derived deterministically from the pairing secret.

The QR is the trust root. The short code is only useful for the manual
fallback flow (the user types the code into the iPhone app instead of
scanning) — the server still enforces rate limits on the attempt counter,
so brute-forcing a 6-digit space is impractical.
"""

from __future__ import annotations

import hashlib
import hmac

_INFO = b"flightpaper/short-code/v1"


def derive_short_code(pairing_secret: bytes) -> str:
    """Return a ``"XXX-XXX"`` code (six digits, hyphen-separated)."""

    if len(pairing_secret) == 0:
        raise ValueError("pairing_secret must be non-empty")
    digest = hmac.new(pairing_secret, _INFO, hashlib.sha256).digest()
    n = int.from_bytes(digest[:4], "big") % 1_000_000
    return f"{n // 1000:03d}-{n % 1000:03d}"


__all__ = ["derive_short_code"]
