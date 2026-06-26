"""``/api/public/*`` — unauthenticated routes (rate-limited at framework level).

These endpoints MUST NOT leak any session secret, GPS data, or
configuration. The handshake endpoint validates the envelope under the
**symmetric pairing key** (see ``packages/protocol/protocol.md`` §3.3).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .. import __version__ as PACKAGE_VERSION
from ..hardware.system_info import host_uptime_seconds
from ..security import crypto
from ..security.crypto import (
    AEAD_KEY_BYTES,
    AEAD_NONCE_BYTES,
    DecryptionError,
    b64u_decode,
)
from ..security.pairing import PairingExpired
from ..utils.time_utils import now_ts
from .app_state import AppState
from .auth import get_state, http_status_for
from .schemas import (
    HealthResponse,
    PairingStatusResponse,
    PairRequest,
    PairResponseBody,
    error_dict,
)
from .secure_envelope import (
    ENVELOPE_VERSION,
    EnvelopeSchemaError,
    build_aad,
    encrypt_envelope,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])

_CLIENT_ID_PATTERN = re.compile(r"^iphone_[0-9a-f]{12}$")
_DEVICE_ID_PATTERN = re.compile(r"^fp_[0-9a-f]{8}$")


# ---------------------------------------------------------------------------
# Health + pairing status
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    state: AppState = get_state(request)
    return HealthResponse(
        ok=True,
        device_id=state.identity.device_id,
        version=state.config.app.version,
        uptime_seconds=host_uptime_seconds(),
    )


@router.get("/pairing-status", response_model=PairingStatusResponse)
def pairing_status(request: Request) -> PairingStatusResponse:
    state: AppState = get_state(request)
    status = state.pairing.status()
    return PairingStatusResponse(**status)


# ---------------------------------------------------------------------------
# Pair handshake
# ---------------------------------------------------------------------------


def _validate_pair_envelope_shape(env: Any, *, expected_device_id: str) -> dict[str, Any]:
    """Validate just enough of the envelope shape to attempt decryption.

    A full schema validation lives in :mod:`flightpaper.api.secure_envelope`
    but it rejects ``key_id != "main"``. The pair endpoint accepts only
    ``key_id == "pairing"`` so we duplicate the basic checks here.
    """

    if not isinstance(env, dict):
        raise EnvelopeSchemaError("envelope must be a JSON object")
    for field in ("v", "device_id", "client_id", "key_id", "seq", "ts", "nonce", "ciphertext"):
        if field not in env:
            raise EnvelopeSchemaError(f"missing field: {field}")
    if env["v"] != ENVELOPE_VERSION:
        raise EnvelopeSchemaError("unsupported version")
    if not isinstance(env["device_id"], str) or not _DEVICE_ID_PATTERN.fullmatch(env["device_id"]):
        raise EnvelopeSchemaError("device_id format invalid")
    if env["device_id"] != expected_device_id:
        raise EnvelopeSchemaError("device_id mismatch")
    if not isinstance(env["client_id"], str) or not _CLIENT_ID_PATTERN.fullmatch(env["client_id"]):
        raise EnvelopeSchemaError("client_id format invalid")
    if env["key_id"] != "pairing":
        raise EnvelopeSchemaError("key_id must be 'pairing'")
    if not isinstance(env["seq"], int) or env["seq"] < 0:
        raise EnvelopeSchemaError("seq invalid")
    if not isinstance(env["ts"], int):
        raise EnvelopeSchemaError("ts invalid")
    if not isinstance(env["nonce"], str) or not isinstance(env["ciphertext"], str):
        raise EnvelopeSchemaError("nonce/ciphertext must be strings")
    return env


@router.post("/pair")
async def pair(request: Request) -> JSONResponse:
    state: AppState = get_state(request)

    # --- Parse and validate envelope shape ---------------------------------
    try:
        envelope = await request.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail=error_dict("invalid_request"))

    try:
        envelope = _validate_pair_envelope_shape(envelope, expected_device_id=state.identity.device_id)
    except EnvelopeSchemaError as exc:
        log.debug("pair envelope rejected: %s", exc)
        raise HTTPException(
            status_code=http_status_for("bad_envelope"),
            detail=error_dict("bad_envelope"),
        ) from exc

    # --- Look up the pairing key -------------------------------------------
    try:
        pairing_key = state.pairing.get_pairing_key()
    except PairingExpired:
        raise HTTPException(
            status_code=http_status_for("pairing_expired"),
            detail=error_dict("pairing_expired"),
        )

    # --- Decrypt the envelope ----------------------------------------------
    try:
        nonce = b64u_decode(envelope["nonce"])
        ciphertext = b64u_decode(envelope["ciphertext"])
    except crypto.CryptoError:
        raise HTTPException(
            status_code=http_status_for("bad_envelope"),
            detail=error_dict("bad_envelope"),
        )
    if len(nonce) != AEAD_NONCE_BYTES:
        raise HTTPException(
            status_code=http_status_for("bad_envelope"),
            detail=error_dict("bad_envelope"),
        )

    aad = build_aad(
        v=ENVELOPE_VERSION,
        method="POST",
        path=request.url.path,
        device_id=envelope["device_id"],
        client_id=envelope["client_id"],
        key_id="pairing",
        seq=int(envelope["seq"]),
        ts=int(envelope["ts"]),
    )
    try:
        plaintext = crypto.aead_decrypt(
            key=pairing_key,
            nonce=nonce,
            ciphertext=ciphertext,
            aad=aad,
        )
    except DecryptionError:
        killed = state.pairing.record_attempt_failure()
        if killed:
            raise HTTPException(
                status_code=http_status_for("attempt_limit"),
                detail=error_dict("attempt_limit"),
            )
        raise HTTPException(
            status_code=http_status_for("bad_envelope"),
            detail=error_dict("bad_envelope"),
        )

    # --- Parse plaintext into PairRequest ----------------------------------
    try:
        raw = json.loads(plaintext.decode("utf-8"))
        pair_req = PairRequest.model_validate(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        log.debug("pair plaintext invalid: %s", exc)
        raise HTTPException(
            status_code=http_status_for("invalid_request"),
            detail=error_dict("invalid_request"),
        )

    try:
        client_pub = b64u_decode(pair_req.client_pub)
    except crypto.CryptoError:
        raise HTTPException(
            status_code=http_status_for("invalid_request"),
            detail=error_dict("invalid_request"),
        )
    if len(client_pub) != AEAD_KEY_BYTES:  # X25519 public key is also 32 bytes
        raise HTTPException(
            status_code=http_status_for("invalid_request"),
            detail=error_dict("invalid_request"),
        )

    # --- Complete the handshake --------------------------------------------
    try:
        paired_client = state.pairing.complete(
            client_id=envelope["client_id"],
            client_public_key=client_pub,
            app_instance_name=pair_req.app_instance_name,
        )
    except PairingExpired:
        raise HTTPException(
            status_code=http_status_for("pairing_expired"),
            detail=error_dict("pairing_expired"),
        )

    # Page jumps from pairing → default after successful pair.
    state.current_page = state.config.display.default_page
    state.force_refresh = True

    # --- Build response envelope (still encrypted under pairing_key) -------
    response_body = PairResponseBody(
        device_id=state.identity.device_id,
        client_id=paired_client.client_id,
        paired_at=paired_client.paired_at,
        session_starts_at_seq=1,
    ).model_dump(mode="json")

    response_envelope = encrypt_envelope(
        plaintext=json.dumps(response_body, separators=(",", ":")).encode("utf-8"),
        key=pairing_key,
        method="RES",
        path=request.url.path,
        device_id=state.identity.device_id,
        client_id=paired_client.client_id,
        key_id="pairing",
        seq=0,
        ts=now_ts(),
    )
    log.info("paired client_id=%s", paired_client.client_id)
    return JSONResponse(response_envelope)


__all__ = ["router"]
