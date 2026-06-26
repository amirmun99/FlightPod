"""FastAPI helpers for envelope verification + response sealing.

Routes use :func:`open_secure_envelope` to verify an incoming envelope and
:func:`seal_response` to encrypt a response. These thin wrappers translate
:mod:`flightpaper.api.secure_envelope` exceptions into HTTP responses while
keeping the route handlers free of crypto code.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from ..utils.time_utils import now_ts
from .app_state import AppState
from .schemas import error_dict
from .secure_envelope import (
    ENVELOPE_VERSION,
    EnvelopeError,
    EnvelopeOpenResult,
    EnvelopeSchemaError,
    EnvelopeVerificationError,
    RESPONSE_METHOD,
    open_envelope,
    seal_envelope,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State accessor
# ---------------------------------------------------------------------------


def get_state(request: Request) -> AppState:
    """Return the singleton AppState attached at startup."""

    return request.app.state.flightpaper  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Error → HTTP mapping
# ---------------------------------------------------------------------------


_HTTP_FOR_CODE: dict[str, int] = {
    "not_paired": 401,
    "bad_envelope": 401,
    "replay": 401,
    "expired": 401,
    "pairing_expired": 410,
    "attempt_limit": 429,
    "invalid_request": 400,
    "not_ready": 503,
    "forbidden_action": 403,
    "internal": 500,
}


def http_status_for(code: str) -> int:
    return _HTTP_FOR_CODE.get(code, 400)


def http_for_envelope_error(exc: EnvelopeError) -> int:
    return http_status_for(exc.code)


# ---------------------------------------------------------------------------
# Envelope opening (raises HTTPException with a clean error body)
# ---------------------------------------------------------------------------


async def open_secure_envelope(request: Request) -> EnvelopeOpenResult:
    """Parse + verify the request body as a secure envelope.

    Returns the :class:`EnvelopeOpenResult`. Raises :class:`HTTPException`
    with a generic error body on any failure — no internal detail leaks.
    """

    state = get_state(request)
    # Browsers and Node.js refuse to send a body on GET. To keep the wire
    # format uniform we accept the envelope either as the JSON body (POST /
    # PATCH) or as a base64url-JSON ``?e=`` query parameter (GET).
    body: Any = None
    raw_query_envelope = request.query_params.get("e")
    if raw_query_envelope is not None:
        try:
            from ..security.crypto import b64u_decode  # local import; avoid cycles
            body = json.loads(b64u_decode(raw_query_envelope).decode("utf-8"))
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=error_dict("invalid_request"))
    else:
        try:
            body = await request.json()
        except (ValueError, json.JSONDecodeError) as exc:
            log.debug("invalid_json on %s: %s", request.url.path, exc)
            raise HTTPException(status_code=400, detail=error_dict("invalid_request"))

    try:
        return open_envelope(
            body,
            method=request.method.upper(),
            path=request.url.path,
            key_store=state.key_store,
            replay=state.replay,
            now=now_ts(),
            expected_device_id=state.identity.device_id,
        )
    except EnvelopeSchemaError as exc:
        raise HTTPException(
            status_code=http_status_for("bad_envelope"),
            detail=error_dict("bad_envelope"),
        ) from exc
    except EnvelopeVerificationError as exc:
        log.debug("envelope rejected on %s: %s", request.url.path, exc.code)
        raise HTTPException(
            status_code=http_for_envelope_error(exc),
            detail=error_dict(exc.code),
        ) from exc


# ---------------------------------------------------------------------------
# Response sealing
# ---------------------------------------------------------------------------


def seal_response(
    *,
    state: AppState,
    request: Request,
    opened: EnvelopeOpenResult,
    body: dict[str, Any] | list[Any],
    status_code: int = 200,
) -> JSONResponse:
    """Encrypt ``body`` under the paired client's session key + return JSON."""

    seq = state.key_store.claim_seq_out(opened.client.client_id)
    envelope = seal_envelope(
        payload=body,
        key=opened.client.session_key,
        method=RESPONSE_METHOD,
        path=request.url.path,
        device_id=state.identity.device_id,
        client_id=opened.client.client_id,
        key_id="main",
        seq=seq,
        ts=now_ts(),
    )
    return JSONResponse(envelope, status_code=status_code)


# ---------------------------------------------------------------------------
# Plaintext parsing for decrypted bodies
# ---------------------------------------------------------------------------


def parse_plaintext_json(plaintext: bytes) -> dict[str, Any]:
    """Decode an envelope plaintext as a JSON object. Raises HTTP 400 on failure."""

    try:
        decoded = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400, detail=error_dict("invalid_request")
        ) from exc
    if not isinstance(decoded, dict):
        raise HTTPException(
            status_code=400, detail=error_dict("invalid_request")
        )
    return decoded


__all__ = [
    "ENVELOPE_VERSION",
    "get_state",
    "http_for_envelope_error",
    "http_status_for",
    "open_secure_envelope",
    "parse_plaintext_json",
    "seal_response",
]
