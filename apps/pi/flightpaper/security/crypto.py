"""Cryptographic primitives used throughout FlightPaper.

This module wraps libsodium (via PyNaCl) for X25519 ECDH and
XChaCha20-Poly1305 AEAD, and implements HKDF-SHA256 with stdlib HMAC
(RFC 5869). No code in this module invents a primitive.

Why XChaCha20-Poly1305 rather than ChaCha20-Poly1305 (IETF, 12-byte nonces)?
We chose 24-byte (192-bit) nonces in ``packages/protocol/protocol.md`` so
that envelopes can use random nonces safely without a counter — the IETF
variant's 96-bit nonce space is too small for unconstrained random reuse
across long-lived session keys.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from nacl import bindings, exceptions, public  # type: ignore[import-untyped]

# Byte sizes the protocol relies on.
AEAD_KEY_BYTES: int = 32         # XChaCha20-Poly1305 key
AEAD_NONCE_BYTES: int = 24       # XChaCha20-Poly1305 nonce
AEAD_TAG_BYTES: int = 16         # Poly1305 tag
PAIRING_SECRET_BYTES: int = 32   # 256-bit one-time secret

# HKDF info strings. Versioned so we can rotate later.
_HKDF_PAIR_INFO: bytes = b"flightpaper/pair/v1"
_HKDF_SESSION_INFO_PREFIX: bytes = b"flightpaper/session/v1|"


class CryptoError(Exception):
    """Generic crypto error (precondition failed, bad input size)."""


class DecryptionError(CryptoError):
    """AEAD verification or decryption failed (bad tag, bad key, tampered)."""


@dataclass(frozen=True)
class X25519KeyPair:
    """A serialized X25519 keypair. ``private_key`` is the 32-byte scalar
    (NOT a long-term identity hash) and ``public_key`` is its Curve25519
    public point.
    """

    private_key: bytes
    public_key: bytes

    def __post_init__(self) -> None:  # pragma: no cover - dataclass invariant
        if len(self.private_key) != 32:
            raise CryptoError("X25519 private key must be 32 bytes")
        if len(self.public_key) != 32:
            raise CryptoError("X25519 public key must be 32 bytes")


# ---------------------------------------------------------------------------
# X25519 ECDH
# ---------------------------------------------------------------------------


def generate_x25519_keypair() -> X25519KeyPair:
    """Generate a fresh X25519 keypair using libsodium's CSPRNG."""

    priv = public.PrivateKey.generate()
    return X25519KeyPair(
        private_key=bytes(priv.encode()),
        public_key=bytes(priv.public_key.encode()),
    )


def x25519_shared_secret(*, private_key: bytes, peer_public_key: bytes) -> bytes:
    """Compute the X25519 shared secret using a raw scalar multiplication.

    Returns the 32-byte ``X25519(priv, peer_pub)`` value, which MUST be fed
    into HKDF before being used as an encryption key.
    """

    if len(private_key) != 32:
        raise CryptoError("X25519 private key must be 32 bytes")
    if len(peer_public_key) != 32:
        raise CryptoError("X25519 peer public key must be 32 bytes")
    return bindings.crypto_scalarmult(private_key, peer_public_key)


# ---------------------------------------------------------------------------
# HKDF-SHA256 (RFC 5869)
# ---------------------------------------------------------------------------


def hkdf_sha256(
    *,
    ikm: bytes,
    salt: bytes,
    info: bytes,
    length: int = AEAD_KEY_BYTES,
) -> bytes:
    """Standard HKDF-SHA256 (extract + expand)."""

    if length <= 0:
        raise CryptoError("HKDF length must be > 0")
    if length > 255 * 32:
        raise CryptoError("HKDF length too large for SHA-256")

    # Extract: if salt is empty, RFC 5869 defines a zero-byte salt.
    salt_or_zero = salt if salt else b"\x00" * 32
    prk = hmac.new(salt_or_zero, ikm, hashlib.sha256).digest()

    # Expand.
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        okm += t
        counter += 1
    return okm[:length]


def derive_pairing_key(
    *,
    pairing_secret: bytes,
    device_id: str,
    device_public_key: bytes,
) -> bytes:
    """Derive the symmetric AEAD key used during the pairing handshake.

    Both sides know ``pairing_secret`` (from the QR), ``device_id``, and
    ``device_public_key`` (also from the QR). Binding the key to the device
    identity prevents a captured pairing secret from being replayed against
    a different physical device.

    This intentionally does NOT use ECDH — the chicken-and-egg of "the
    envelope is encrypted with a key that depends on ``client_pub`` but
    ``client_pub`` lives inside that envelope" forces the pairing key to be
    symmetric. ECDH happens afterwards for the session key (see
    :func:`derive_session_key`), which is where forward-secrecy-like
    properties live in v1.
    """

    if len(device_public_key) != 32:
        raise CryptoError("device_public_key must be 32 bytes")
    salt = device_id.encode("utf-8") + b"|" + device_public_key
    return hkdf_sha256(
        ikm=pairing_secret,
        salt=salt,
        info=_HKDF_PAIR_INFO,
        length=AEAD_KEY_BYTES,
    )


def derive_session_key(
    *,
    shared_secret: bytes,
    pairing_secret: bytes,
    device_id: str,
    client_id: str,
) -> bytes:
    """Derive the long-term session key for one (device, client) pair."""

    info = _HKDF_SESSION_INFO_PREFIX + device_id.encode() + b"|" + client_id.encode()
    return hkdf_sha256(
        ikm=shared_secret,
        salt=pairing_secret,
        info=info,
        length=AEAD_KEY_BYTES,
    )


# ---------------------------------------------------------------------------
# Random helpers
# ---------------------------------------------------------------------------


def random_pairing_secret() -> bytes:
    return secrets.token_bytes(PAIRING_SECRET_BYTES)


def random_nonce() -> bytes:
    """Fresh 24-byte AEAD nonce. Safe under randoms for XChaCha20-Poly1305."""

    return secrets.token_bytes(AEAD_NONCE_BYTES)


# ---------------------------------------------------------------------------
# AEAD: XChaCha20-Poly1305 (IETF)
# ---------------------------------------------------------------------------


def aead_encrypt(*, key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Encrypt ``plaintext`` with associated data ``aad``.

    Returns ``ciphertext || tag`` (libsodium's standard layout).
    """

    if len(key) != AEAD_KEY_BYTES:
        raise CryptoError("AEAD key must be 32 bytes")
    if len(nonce) != AEAD_NONCE_BYTES:
        raise CryptoError("AEAD nonce must be 24 bytes")
    return bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(
        plaintext, aad, nonce, key
    )


def aead_decrypt(*, key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """Verify and decrypt. Raises :class:`DecryptionError` on any failure."""

    if len(key) != AEAD_KEY_BYTES:
        raise CryptoError("AEAD key must be 32 bytes")
    if len(nonce) != AEAD_NONCE_BYTES:
        raise CryptoError("AEAD nonce must be 24 bytes")
    if len(ciphertext) < AEAD_TAG_BYTES:
        raise DecryptionError("ciphertext shorter than tag")
    try:
        return bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(
            ciphertext, aad, nonce, key
        )
    except exceptions.CryptoError as exc:
        raise DecryptionError("AEAD verification failed") from exc


# ---------------------------------------------------------------------------
# Constant-time comparison + base64url
# ---------------------------------------------------------------------------


def constant_time_eq(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


def b64u_encode(data: bytes) -> str:
    """RFC 7515-style base64url encoding with no padding."""

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(s: str) -> bytes:
    """Tolerant base64url decoder (handles missing padding)."""

    if not isinstance(s, str):
        raise CryptoError("b64u_decode expects str")
    pad = (-len(s)) % 4
    try:
        return base64.urlsafe_b64decode(s + ("=" * pad))
    except (ValueError, base64.binascii.Error) as exc:
        raise CryptoError(f"invalid base64url: {exc}") from exc


__all__ = [
    "AEAD_KEY_BYTES",
    "AEAD_NONCE_BYTES",
    "AEAD_TAG_BYTES",
    "PAIRING_SECRET_BYTES",
    "CryptoError",
    "DecryptionError",
    "X25519KeyPair",
    "aead_decrypt",
    "aead_encrypt",
    "b64u_decode",
    "b64u_encode",
    "constant_time_eq",
    "derive_pairing_key",
    "derive_session_key",
    "generate_x25519_keypair",
    "hkdf_sha256",
    "random_nonce",
    "random_pairing_secret",
    "x25519_shared_secret",
]
