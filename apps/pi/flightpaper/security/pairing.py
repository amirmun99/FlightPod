"""Pairing state machine + QR URI builder/parser.

State graph (see ``packages/protocol/protocol.md`` §3.1):

    unpaired ──start──▶ pairing_pending ──complete──▶ paired
       ▲                      │
       │                      └── expire / reset ──┘

The state machine owns ``pairing_state.json`` and delegates paired-client
records to :class:`KeyStore`. ``unpaired`` and ``pairing_pending`` are
indistinguishable from the outside until a QR has been minted; ``paired``
means at least one client exists in :class:`KeyStore`.
"""

from __future__ import annotations

import base64
import enum
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from . import crypto
from ._secure_io import atomic_write_json, read_json
from .device_identity import DeviceIdentity
from .key_store import KeyStore, PairedClient
from .replay import ReplayWindow
from .tokens import derive_short_code

log = logging.getLogger(__name__)

_FILENAME = "pairing_state.json"
_PROTOCOL_VERSION = 1


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PairingFailed(Exception):
    """Pairing handshake rejected by the server."""


class PairingExpired(PairingFailed):
    """One-time pairing secret expired or was never minted."""


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class PairingStatus(str, enum.Enum):
    UNPAIRED = "unpaired"
    PAIRING_PENDING = "pairing_pending"
    PAIRED = "paired"


@dataclass
class PairingState:
    status: PairingStatus = PairingStatus.UNPAIRED
    pairing_secret: bytes | None = None
    pairing_nonce: bytes | None = None
    expires_at: int | None = None
    attempt_count: int = 0
    started_at: int | None = None

    def to_disk(self) -> dict[str, Any]:
        # Persist enough to resume the pairing window across a restart.
        return {
            "status": self.status.value,
            "pairing_secret": (
                crypto.b64u_encode(self.pairing_secret)
                if self.pairing_secret is not None
                else None
            ),
            "pairing_nonce": (
                crypto.b64u_encode(self.pairing_nonce)
                if self.pairing_nonce is not None
                else None
            ),
            "expires_at": self.expires_at,
            "attempt_count": self.attempt_count,
            "started_at": self.started_at,
        }

    @classmethod
    def from_disk(cls, raw: dict[str, Any]) -> "PairingState":
        return cls(
            status=PairingStatus(raw.get("status", PairingStatus.UNPAIRED.value)),
            pairing_secret=(
                crypto.b64u_decode(raw["pairing_secret"])
                if raw.get("pairing_secret")
                else None
            ),
            pairing_nonce=(
                crypto.b64u_decode(raw["pairing_nonce"])
                if raw.get("pairing_nonce")
                else None
            ),
            expires_at=raw.get("expires_at"),
            attempt_count=int(raw.get("attempt_count", 0)),
            started_at=raw.get("started_at"),
        )


# ---------------------------------------------------------------------------
# QR URI
# ---------------------------------------------------------------------------

_PAIR_URI_SCHEME = "flightpaper"
_PAIR_URI_HOST = "pair"


def build_pair_uri(payload: dict[str, Any]) -> str:
    """Encode ``payload`` as ``flightpaper://pair?p=<base64url(JSON)>``."""

    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    return f"{_PAIR_URI_SCHEME}://{_PAIR_URI_HOST}?p={encoded}"


def parse_pair_uri(uri: str) -> dict[str, Any]:
    """Inverse of :func:`build_pair_uri`. Raises ``ValueError`` on malformed input."""

    parts = urlsplit(uri)
    if parts.scheme != _PAIR_URI_SCHEME:
        raise ValueError(f"unexpected scheme: {parts.scheme!r}")
    if parts.netloc != _PAIR_URI_HOST and parts.hostname != _PAIR_URI_HOST:
        raise ValueError(f"unexpected host: {parts.netloc!r}")
    qs = parse_qs(parts.query, keep_blank_values=False)
    encoded = qs.get("p", [None])[0]
    if not encoded:
        raise ValueError("missing 'p' parameter")
    try:
        raw = crypto.b64u_decode(encoded)
        return json.loads(raw.decode("utf-8"))
    except (crypto.CryptoError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"invalid 'p' payload: {exc}") from exc


# ---------------------------------------------------------------------------
# Pairing manager
# ---------------------------------------------------------------------------


class PairingManager:
    """Owns the pairing state file + delegates persistence to :class:`KeyStore`.

    Parameters
    ----------
    secure_dir: directory under which all security state lives.
    identity:   long-term device identity (provides device public key).
    key_store:  paired-client persistence.
    replay:     replay window (cleared on pair/reset).
    host_provider: callable returning current ``(host, port)`` for the QR.
    expires_seconds: lifetime of a pairing window.
    max_attempts:    bad-secret attempts allowed before the secret is killed.
    time_fn:    injectable clock for tests.
    """

    def __init__(
        self,
        *,
        secure_dir: Path,
        identity: DeviceIdentity,
        key_store: KeyStore,
        replay: ReplayWindow | None = None,
        host_provider: Callable[[], tuple[str, int]] = lambda: ("0.0.0.0", 8080),
        expires_seconds: int = 600,
        max_attempts: int = 5,
        time_fn: Callable[[], int] = lambda: int(time.time()),
    ) -> None:
        if expires_seconds <= 0:
            raise ValueError("expires_seconds must be > 0")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be > 0")
        self._secure_dir = secure_dir
        self._path = secure_dir / _FILENAME
        self._identity = identity
        self._key_store = key_store
        self._replay = replay
        self._host_provider = host_provider
        self._expires_s = expires_seconds
        self._max_attempts = max_attempts
        self._time_fn = time_fn
        self._lock = RLock()
        self._state = self._load_state()
        self._reconcile_locked()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _load_state(self) -> PairingState:
        if not self._path.exists():
            return PairingState()
        try:
            raw = read_json(self._path)
        except (OSError, ValueError) as exc:
            log.warning("pairing_state.json unreadable; resetting: %s", exc)
            return PairingState()
        try:
            return PairingState.from_disk(raw)
        except (KeyError, ValueError, crypto.CryptoError) as exc:
            log.warning("pairing_state.json invalid; resetting: %s", exc)
            return PairingState()

    def _save_state_locked(self) -> None:
        atomic_write_json(self._path, self._state.to_disk())

    def _reconcile_locked(self) -> None:
        """Bring the in-memory state in line with on-disk pairing artifacts.

        - If pending window has expired, drop back to ``unpaired``.
        - If at least one paired client exists, reflect ``paired``.
        """

        now = self._time_fn()

        if (
            self._state.status == PairingStatus.PAIRING_PENDING
            and self._state.expires_at is not None
            and now > self._state.expires_at
        ):
            log.info("pairing window expired; reverting to unpaired")
            self._state = PairingState()
            self._save_state_locked()

        if self._key_store.count() > 0:
            self._state.status = PairingStatus.PAIRED
            self._save_state_locked()

    # ------------------------------------------------------------------
    # Public status
    # ------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._reconcile_locked()
            return {
                "state": self._state.status.value,
                "device_id": self._identity.device_id,
                "device_name": self._identity.device_name,
                "pairing_expires_at": self._state.expires_at,
                "protocol_version": _PROTOCOL_VERSION,
            }

    def is_paired(self) -> bool:
        with self._lock:
            self._reconcile_locked()
            return self._state.status == PairingStatus.PAIRED

    # ------------------------------------------------------------------
    # Pairing window lifecycle
    # ------------------------------------------------------------------

    def start(self) -> PairingState:
        """Mint a new one-time secret + nonce and enter ``pairing_pending``."""

        with self._lock:
            now = self._time_fn()
            self._state = PairingState(
                status=PairingStatus.PAIRING_PENDING,
                pairing_secret=crypto.random_pairing_secret(),
                pairing_nonce=crypto.random_nonce(),
                expires_at=now + self._expires_s,
                attempt_count=0,
                started_at=now,
            )
            self._save_state_locked()
            log.info("pairing window opened (expires_at=%s)", self._state.expires_at)
            return self._state

    def reset(self) -> None:
        """Wipe paired clients and pairing state. Display jumps to QR page."""

        with self._lock:
            self._key_store.clear()
            self._state = PairingState()
            self._save_state_locked()
            if self._replay is not None:
                self._replay.clear()
            log.info("pairing reset; device is unpaired")

    # ------------------------------------------------------------------
    # QR payload
    # ------------------------------------------------------------------

    def qr_payload(self) -> dict[str, Any]:
        """Build the payload that goes inside the QR (post-encoding)."""

        with self._lock:
            if (
                self._state.status != PairingStatus.PAIRING_PENDING
                or self._state.pairing_secret is None
                or self._state.expires_at is None
            ):
                raise PairingExpired("no pairing window open")
            host, port = self._host_provider()
            return {
                "v": _PROTOCOL_VERSION,
                "host": host,
                "port": int(port),
                "device_id": self._identity.device_id,
                "device_name": self._identity.device_name[:32],
                "device_pub": crypto.b64u_encode(self._identity.public_key),
                "pairing_secret": crypto.b64u_encode(self._state.pairing_secret),
                "expires_at": int(self._state.expires_at),
                "code": derive_short_code(self._state.pairing_secret),
            }

    def qr_uri(self) -> str:
        return build_pair_uri(self.qr_payload())

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

    def get_pairing_key(self) -> bytes:
        """Return the symmetric AEAD key for the current pairing window.

        Raises :class:`PairingExpired` if no window is open or it has
        expired. The caller MUST cache the returned key before invoking
        :meth:`complete`, since ``complete`` destroys the pairing secret.
        """

        with self._lock:
            self._reconcile_locked()
            if (
                self._state.status != PairingStatus.PAIRING_PENDING
                or self._state.pairing_secret is None
            ):
                raise PairingExpired("no pairing window open")
            now = self._time_fn()
            if self._state.expires_at is not None and now > self._state.expires_at:
                raise PairingExpired("pairing window expired")
            return crypto.derive_pairing_key(
                pairing_secret=self._state.pairing_secret,
                device_id=self._identity.device_id,
                device_public_key=self._identity.public_key,
            )

    def record_attempt_failure(self) -> bool:
        """Increment the attempt counter; return ``True`` if window now killed."""

        with self._lock:
            if self._state.status != PairingStatus.PAIRING_PENDING:
                return True
            self._state.attempt_count += 1
            if self._state.attempt_count >= self._max_attempts:
                log.warning("pairing attempt limit reached; invalidating secret")
                self._state = PairingState()
                self._save_state_locked()
                return True
            self._save_state_locked()
            return False

    def complete(
        self,
        *,
        client_id: str,
        client_public_key: bytes,
        app_instance_name: str | None = None,
    ) -> PairedClient:
        """Finalize the handshake: derive session key, persist, kill the secret."""

        with self._lock:
            if (
                self._state.status != PairingStatus.PAIRING_PENDING
                or self._state.pairing_secret is None
            ):
                raise PairingExpired("no pairing window open")
            now = self._time_fn()
            if self._state.expires_at is not None and now > self._state.expires_at:
                raise PairingExpired("pairing window expired")

            shared = crypto.x25519_shared_secret(
                private_key=self._identity.private_key,
                peer_public_key=client_public_key,
            )
            session_key = crypto.derive_session_key(
                shared_secret=shared,
                pairing_secret=self._state.pairing_secret,
                device_id=self._identity.device_id,
                client_id=client_id,
            )

            client = PairedClient(
                client_id=client_id,
                client_public_key=client_public_key,
                session_key=session_key,
                paired_at=now,
                last_seen_at=now,
                last_seq_in=0,
                next_seq_out=1,
                app_instance_name=app_instance_name,
            )
            self._key_store.add(client)

            # Burn the one-time secret immediately.
            self._state = PairingState(status=PairingStatus.PAIRED)
            self._save_state_locked()

            if self._replay is not None:
                self._replay.reset_client(client_id)

            log.info("pairing completed for client_id=%s", client_id)
            return client


__all__ = [
    "PairingExpired",
    "PairingFailed",
    "PairingManager",
    "PairingState",
    "PairingStatus",
    "build_pair_uri",
    "parse_pair_uri",
]
