"""HTTP API layer (FastAPI). Phase 4 adds only the secure-envelope helpers;
Phase 5 wires up the routes and ASGI app.
"""

from .secure_envelope import (
    EnvelopeError,
    EnvelopeOpenResult,
    EnvelopeSchemaError,
    EnvelopeVerificationError,
    encrypt_envelope,
    open_envelope,
    seal_envelope,
)

__all__ = [
    "EnvelopeError",
    "EnvelopeOpenResult",
    "EnvelopeSchemaError",
    "EnvelopeVerificationError",
    "encrypt_envelope",
    "open_envelope",
    "seal_envelope",
]
