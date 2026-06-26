"""Security subsystem: crypto primitives, identity, pairing, replay protection.

Everything in this package is intended to be cryptographically auditable.
Hand-rolled primitives are not allowed; we wrap libsodium (via PyNaCl) for
AEAD and X25519 ECDH and stdlib ``hmac``/``hashlib`` for HKDF (RFC 5869).
"""

from .crypto import (
    AEAD_KEY_BYTES,
    AEAD_NONCE_BYTES,
    AEAD_TAG_BYTES,
    PAIRING_SECRET_BYTES,
    CryptoError,
    DecryptionError,
    X25519KeyPair,
    aead_decrypt,
    aead_encrypt,
    b64u_decode,
    b64u_encode,
    constant_time_eq,
    derive_pairing_key,
    derive_session_key,
    generate_x25519_keypair,
    hkdf_sha256,
    random_nonce,
    random_pairing_secret,
    x25519_shared_secret,
)
from .device_identity import (
    DeviceIdentity,
    create_identity,
    load_identity,
    load_or_create_identity,
    save_identity,
)
from .key_store import KeyStore, PairedClient
from .pairing import (
    PairingExpired,
    PairingFailed,
    PairingManager,
    PairingState,
    PairingStatus,
    build_pair_uri,
    parse_pair_uri,
)
from .replay import ReplayCheckResult, ReplayWindow
from .tokens import derive_short_code

__all__ = [
    "AEAD_KEY_BYTES",
    "AEAD_NONCE_BYTES",
    "AEAD_TAG_BYTES",
    "CryptoError",
    "DecryptionError",
    "DeviceIdentity",
    "KeyStore",
    "PAIRING_SECRET_BYTES",
    "PairedClient",
    "PairingExpired",
    "PairingFailed",
    "PairingManager",
    "PairingState",
    "PairingStatus",
    "ReplayCheckResult",
    "ReplayWindow",
    "X25519KeyPair",
    "aead_decrypt",
    "aead_encrypt",
    "b64u_decode",
    "b64u_encode",
    "build_pair_uri",
    "constant_time_eq",
    "create_identity",
    "derive_pairing_key",
    "derive_session_key",
    "derive_short_code",
    "generate_x25519_keypair",
    "hkdf_sha256",
    "load_identity",
    "load_or_create_identity",
    "parse_pair_uri",
    "random_nonce",
    "random_pairing_secret",
    "save_identity",
    "x25519_shared_secret",
]
