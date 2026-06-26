"""Secure envelope: build, sign, verify.

The envelope shape is normative (see
``packages/protocol/secure-envelope.schema.json``). Every protected
request and response is wrapped in one.

AAD layout (UTF-8 string):

    v=<v>|m=<METHOD>|p=<path>|d=<device_id>|c=<client_id>|k=<key_id>|s=<seq>|t=<ts>

For request envelopes ``method`` is the upper-case HTTP verb. For response
envelopes the spec uses ``"RES"`` so request/response AADs are
distinguishable but symmetric (the ``path`` echoes the request's).
"""

from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from ..security import crypto
from ..security.key_store import KeyStore, PairedClient
from ..security.replay import ReplayCheckResult, ReplayWindow

ENVELOPE_VERSION: int = 1
RESPONSE_METHOD: str = "RES"

_DEVICE_ID_PATTERN = re.compile(r"^fp_[0-9a-f]{8}$")
_CLIENT_ID_PATTERN = re.compile(r"^iphone_[0-9a-f]{12}$")
_ALLOWED_KEY_IDS = ("pairing", "main")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EnvelopeError(Exception):
    """Base class for envelope-handling errors."""

    code: str = "bad_envelope"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message or self.code)
        if code is not None:
            self.code = code


class EnvelopeSchemaError(EnvelopeError):
    """Envelope failed shape validation before any crypto was attempted."""

    code = "bad_envelope"


class EnvelopeVerificationError(EnvelopeError):
    """Envelope shape was OK but verification failed (tag, replay, expiry)."""


class _NotPairedError(EnvelopeVerificationError):
    code = "not_paired"


class _ReplayError(EnvelopeVerificationError):
    code = "replay"


class _ExpiredError(EnvelopeVerificationError):
    code = "expired"


class _BadTagError(EnvelopeVerificationError):
    code = "bad_envelope"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def build_aad(
    *,
    v: int,
    method: str,
    path: str,
    device_id: str,
    client_id: str,
    key_id: str,
    seq: int,
    ts: int,
) -> bytes:
    """Build the canonical AAD string for an envelope."""

    parts = (
        f"v={v}",
        f"m={method}",
        f"p={path}",
        f"d={device_id}",
        f"c={client_id}",
        f"k={key_id}",
        f"s={seq}",
        f"t={ts}",
    )
    return "|".join(parts).encode("utf-8")


def encrypt_envelope(
    *,
    plaintext: bytes,
    key: bytes,
    method: str,
    path: str,
    device_id: str,
    client_id: str,
    key_id: str,
    seq: int,
    ts: int,
    v: int = ENVELOPE_VERSION,
    nonce: bytes | None = None,
) -> dict[str, Any]:
    """Encrypt one envelope. Returns the JSON-serializable dict."""

    nonce_bytes = nonce if nonce is not None else crypto.random_nonce()
    aad = build_aad(
        v=v,
        method=method,
        path=path,
        device_id=device_id,
        client_id=client_id,
        key_id=key_id,
        seq=seq,
        ts=ts,
    )
    ciphertext = crypto.aead_encrypt(
        key=key,
        nonce=nonce_bytes,
        plaintext=plaintext,
        aad=aad,
    )
    return {
        "v": v,
        "device_id": device_id,
        "client_id": client_id,
        "key_id": key_id,
        "seq": seq,
        "ts": ts,
        "nonce": crypto.b64u_encode(nonce_bytes),
        "ciphertext": crypto.b64u_encode(ciphertext),
    }


def seal_envelope(
    *,
    payload: Mapping[str, Any] | list[Any],
    key: bytes,
    method: str,
    path: str,
    device_id: str,
    client_id: str,
    key_id: str,
    seq: int,
    ts: int,
) -> dict[str, Any]:
    """Convenience: JSON-serialize ``payload`` then call :func:`encrypt_envelope`."""

    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return encrypt_envelope(
        plaintext=plaintext,
        key=key,
        method=method,
        path=path,
        device_id=device_id,
        client_id=client_id,
        key_id=key_id,
        seq=seq,
        ts=ts,
    )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def _require_field(env: Mapping[str, Any], field: str) -> Any:
    if field not in env:
        raise EnvelopeSchemaError(f"missing field: {field}")
    return env[field]


def _validate_schema(env: Mapping[str, Any]) -> None:
    if not isinstance(env, Mapping):
        raise EnvelopeSchemaError("envelope must be a JSON object")

    v = _require_field(env, "v")
    if v != ENVELOPE_VERSION:
        raise EnvelopeSchemaError(f"unsupported envelope version: {v!r}")

    device_id = _require_field(env, "device_id")
    if not isinstance(device_id, str) or not _DEVICE_ID_PATTERN.fullmatch(device_id):
        raise EnvelopeSchemaError("device_id format invalid")

    client_id = _require_field(env, "client_id")
    if not isinstance(client_id, str) or not _CLIENT_ID_PATTERN.fullmatch(client_id):
        raise EnvelopeSchemaError("client_id format invalid")

    key_id = _require_field(env, "key_id")
    if key_id not in _ALLOWED_KEY_IDS:
        raise EnvelopeSchemaError("key_id not allowed")

    seq = _require_field(env, "seq")
    if not isinstance(seq, int) or seq < 0:
        raise EnvelopeSchemaError("seq must be a non-negative integer")

    ts = _require_field(env, "ts")
    if not isinstance(ts, int):
        raise EnvelopeSchemaError("ts must be an integer")

    nonce = _require_field(env, "nonce")
    if not isinstance(nonce, str):
        raise EnvelopeSchemaError("nonce must be base64url string")

    ciphertext = _require_field(env, "ciphertext")
    if not isinstance(ciphertext, str):
        raise EnvelopeSchemaError("ciphertext must be base64url string")


# ---------------------------------------------------------------------------
# Decrypt + verify
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvelopeOpenResult:
    client: PairedClient
    plaintext: bytes
    seq: int
    ts: int
    nonce: bytes


def open_envelope(
    envelope: Mapping[str, Any],
    *,
    method: str,
    path: str,
    key_store: KeyStore,
    replay: ReplayWindow,
    now: int,
    expected_device_id: str | None = None,
) -> EnvelopeOpenResult:
    """Verify an inbound envelope against the key store + replay window.

    Returns the matched paired client and the decrypted plaintext. Updates
    the replay window and the client's ``last_seq_in`` on success.
    """

    _validate_schema(envelope)

    if expected_device_id is not None and envelope["device_id"] != expected_device_id:
        raise _BadTagError("device_id mismatch")

    client = key_store.get(envelope["client_id"])
    if client is None:
        raise _NotPairedError("unknown client")
    if envelope["key_id"] != "main":
        # Pairing key flow is handled separately; this function is only for
        # post-handshake traffic.
        raise EnvelopeSchemaError("non-main key_id rejected by open_envelope")

    try:
        nonce = crypto.b64u_decode(envelope["nonce"])
        ciphertext = crypto.b64u_decode(envelope["ciphertext"])
    except crypto.CryptoError as exc:
        raise EnvelopeSchemaError(f"base64url decode: {exc}") from exc

    if len(nonce) != crypto.AEAD_NONCE_BYTES:
        raise EnvelopeSchemaError("nonce length invalid")

    seq = int(envelope["seq"])
    ts = int(envelope["ts"])

    replay_result = replay.check(
        client_id=client.client_id,
        seq=seq,
        nonce=nonce,
        ts=ts,
        now=now,
        baseline_seq=client.last_seq_in,
    )
    if replay_result == ReplayCheckResult.EXPIRED:
        raise _ExpiredError("timestamp out of window")
    if replay_result == ReplayCheckResult.REPLAY_SEQ:
        raise _ReplayError("seq already used")
    if replay_result == ReplayCheckResult.REPLAY_NONCE:
        raise _ReplayError("nonce already used")
    if replay_result != ReplayCheckResult.OK:
        raise _BadTagError("replay window rejection")

    aad = build_aad(
        v=int(envelope["v"]),
        method=method,
        path=path,
        device_id=envelope["device_id"],
        client_id=envelope["client_id"],
        key_id=envelope["key_id"],
        seq=seq,
        ts=ts,
    )
    try:
        plaintext = crypto.aead_decrypt(
            key=client.session_key,
            nonce=nonce,
            ciphertext=ciphertext,
            aad=aad,
        )
    except crypto.DecryptionError as exc:
        raise _BadTagError("AEAD verification failed") from exc

    # Commit replay state only AFTER successful decryption.
    replay.record(client_id=client.client_id, seq=seq, nonce=nonce)
    key_store.update_seq_in(client.client_id, seq=seq, now=now)

    return EnvelopeOpenResult(
        client=client,
        plaintext=plaintext,
        seq=seq,
        ts=ts,
        nonce=nonce,
    )


# Re-export for star-imports / introspection.
class EnvelopeErrorCode(str, enum.Enum):
    NOT_PAIRED = "not_paired"
    BAD_ENVELOPE = "bad_envelope"
    REPLAY = "replay"
    EXPIRED = "expired"


__all__ = [
    "ENVELOPE_VERSION",
    "EnvelopeError",
    "EnvelopeErrorCode",
    "EnvelopeOpenResult",
    "EnvelopeSchemaError",
    "EnvelopeVerificationError",
    "RESPONSE_METHOD",
    "build_aad",
    "encrypt_envelope",
    "open_envelope",
    "seal_envelope",
]
