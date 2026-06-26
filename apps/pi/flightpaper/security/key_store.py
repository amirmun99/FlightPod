"""Persistent paired-client records.

One record per (device, client) pair. Schema is forward-compatible with
multiple clients, although v1 only exercises a single paired iPhone.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

from . import crypto
from ._secure_io import atomic_write_json, read_json

log = logging.getLogger(__name__)

_FILENAME = "paired_clients.json"
_SCHEMA_VERSION = 1


@dataclass
class PairedClient:
    client_id: str
    client_public_key: bytes  # 32 bytes
    session_key: bytes        # 32 bytes
    paired_at: int
    last_seen_at: int | None = None
    last_seq_in: int = 0
    next_seq_out: int = 1
    app_instance_name: str | None = None

    def __post_init__(self) -> None:
        if len(self.client_public_key) != 32:
            raise ValueError("client_public_key must be 32 bytes")
        if len(self.session_key) != 32:
            raise ValueError("session_key must be 32 bytes")


def _path(secure_dir: Path) -> Path:
    return secure_dir / _FILENAME


def _to_dict(client: PairedClient) -> dict[str, Any]:
    return {
        "client_id": client.client_id,
        "client_public_key": crypto.b64u_encode(client.client_public_key),
        "session_key": crypto.b64u_encode(client.session_key),
        "paired_at": client.paired_at,
        "last_seen_at": client.last_seen_at,
        "last_seq_in": client.last_seq_in,
        "next_seq_out": client.next_seq_out,
        "app_instance_name": client.app_instance_name,
    }


def _from_dict(raw: dict[str, Any]) -> PairedClient:
    return PairedClient(
        client_id=str(raw["client_id"]),
        client_public_key=crypto.b64u_decode(str(raw["client_public_key"])),
        session_key=crypto.b64u_decode(str(raw["session_key"])),
        paired_at=int(raw["paired_at"]),
        last_seen_at=int(raw["last_seen_at"]) if raw.get("last_seen_at") is not None else None,
        last_seq_in=int(raw.get("last_seq_in", 0)),
        next_seq_out=int(raw.get("next_seq_out", 1)),
        app_instance_name=str(raw["app_instance_name"]) if raw.get("app_instance_name") else None,
    )


class KeyStore:
    """Threadsafe registry of paired clients persisted to ``paired_clients.json``."""

    def __init__(self, secure_dir: Path) -> None:
        self._secure_dir = secure_dir
        self._path = _path(secure_dir)
        self._lock = RLock()
        self._clients: dict[str, PairedClient] = {}
        self._load()

    # ------------------------------------------------------------------
    # Disk I/O
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = read_json(self._path)
        except (OSError, ValueError) as exc:
            log.warning("paired_clients.json unreadable; ignoring: %s", exc)
            return
        with self._lock:
            for entry in raw.get("clients", []):
                try:
                    client = _from_dict(entry)
                except (KeyError, ValueError) as exc:
                    log.warning("skipping malformed paired client: %s", exc)
                    continue
                self._clients[client.client_id] = client

    def _save_locked(self) -> None:
        payload = {
            "v": _SCHEMA_VERSION,
            "clients": [_to_dict(c) for c in self._clients.values()],
        }
        atomic_write_json(self._path, payload)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get(self, client_id: str) -> PairedClient | None:
        with self._lock:
            return self._clients.get(client_id)

    def all(self) -> list[PairedClient]:
        with self._lock:
            return list(self._clients.values())

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def add(self, client: PairedClient) -> None:
        with self._lock:
            self._clients[client.client_id] = client
            self._save_locked()

    def update_seq_in(self, client_id: str, *, seq: int, now: int | None = None) -> None:
        with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                return
            if seq > client.last_seq_in:
                client.last_seq_in = seq
            client.last_seen_at = now if now is not None else int(time.time())
            self._save_locked()

    def claim_seq_out(self, client_id: str) -> int:
        """Atomically allocate the next outgoing sequence number."""

        with self._lock:
            client = self._clients.get(client_id)
            if client is None:
                raise KeyError(client_id)
            seq = client.next_seq_out
            client.next_seq_out = seq + 1
            self._save_locked()
            return seq

    def remove(self, client_id: str) -> bool:
        with self._lock:
            if client_id not in self._clients:
                return False
            del self._clients[client_id]
            self._save_locked()
            return True

    def clear(self) -> None:
        with self._lock:
            self._clients.clear()
            self._save_locked()


__all__ = ["KeyStore", "PairedClient"]
