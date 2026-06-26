"""Persistent device identity: device_id + long-term X25519 keypair.

The identity is generated once on first boot and never rotated unless a
human deletes ``device_identity.json``. Rotating it forces every paired
client to re-pair.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from . import crypto
from ._secure_io import atomic_write_json, read_json

log = logging.getLogger(__name__)

_FILENAME = "device_identity.json"
_DEVICE_ID_PATTERN = re.compile(r"^fp_[0-9a-f]{8}$")


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    device_name: str
    private_key: bytes  # 32 bytes (X25519 scalar)
    public_key: bytes   # 32 bytes
    created_at: int

    def __post_init__(self) -> None:
        if not _DEVICE_ID_PATTERN.fullmatch(self.device_id):
            raise ValueError(f"invalid device_id: {self.device_id!r}")
        if len(self.private_key) != 32:
            raise ValueError("private_key must be 32 bytes")
        if len(self.public_key) != 32:
            raise ValueError("public_key must be 32 bytes")


def _path(secure_dir: Path) -> Path:
    return secure_dir / _FILENAME


def _new_device_id() -> str:
    return "fp_" + secrets.token_hex(4)


def create_identity(
    secure_dir: Path,
    *,
    device_name: str = "FlightPaper",
    now_ts: int | None = None,
) -> DeviceIdentity:
    """Generate a new identity and persist it. Overwrites any existing file."""

    keypair = crypto.generate_x25519_keypair()
    identity = DeviceIdentity(
        device_id=_new_device_id(),
        device_name=device_name,
        private_key=keypair.private_key,
        public_key=keypair.public_key,
        created_at=now_ts if now_ts is not None else int(time.time()),
    )
    save_identity(secure_dir, identity)
    log.info("created new device identity: device_id=%s", identity.device_id)
    return identity


def save_identity(secure_dir: Path, identity: DeviceIdentity) -> None:
    atomic_write_json(
        _path(secure_dir),
        {
            "device_id": identity.device_id,
            "device_name": identity.device_name,
            "private_key": crypto.b64u_encode(identity.private_key),
            "public_key": crypto.b64u_encode(identity.public_key),
            "created_at": identity.created_at,
        },
    )


def load_identity(secure_dir: Path) -> DeviceIdentity:
    raw = read_json(_path(secure_dir))
    return DeviceIdentity(
        device_id=str(raw["device_id"]),
        device_name=str(raw.get("device_name", "FlightPaper")),
        private_key=crypto.b64u_decode(str(raw["private_key"])),
        public_key=crypto.b64u_decode(str(raw["public_key"])),
        created_at=int(raw["created_at"]),
    )


def load_or_create_identity(
    secure_dir: Path,
    *,
    device_name: str = "FlightPaper",
) -> DeviceIdentity:
    """Read the identity file; create a fresh one if it's missing."""

    if _path(secure_dir).exists():
        return load_identity(secure_dir)
    return create_identity(secure_dir, device_name=device_name)


__all__ = [
    "DeviceIdentity",
    "create_identity",
    "load_identity",
    "load_or_create_identity",
    "save_identity",
]
