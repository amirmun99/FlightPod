"""Shared atomic-write helpers for files under ``secure_dir``.

Files written here MUST be mode ``0600`` (owner read/write only). On macOS
dev the parent directory is typically ``~/.flightpaper/secure``; on the Pi
it's ``/etc/flightpaper/secure``.

The atomic-write protocol:

1. Open the temp path with ``O_WRONLY | O_CREAT | O_TRUNC`` and explicit mode.
2. Write contents.
3. ``fsync`` if possible.
4. ``os.replace`` to the final path.

The temp file uses the same parent directory so ``os.replace`` is atomic.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_DEFAULT_MODE: int = 0o600


def atomic_write_secure(
    path: Path, content: str, *, mode: int = _DEFAULT_MODE
) -> None:
    """Atomically write ``content`` to ``path`` with restrictive permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    # Tighten directory permissions if we can; ignore failure (root-only paths).
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass

    tmp = path.with_name(path.name + ".tmp")
    # ``os.O_TRUNC`` so we overwrite any leftover tmp from a previous failure.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
    except Exception:
        # Best-effort cleanup of the temp file on write failure.
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    os.replace(tmp, path)
    # `os.replace` preserves the mode set on the temp file.


def atomic_write_json(path: Path, payload: Any, *, mode: int = _DEFAULT_MODE) -> None:
    atomic_write_secure(path, json.dumps(payload, indent=2, sort_keys=True), mode=mode)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


__all__ = ["atomic_write_secure", "atomic_write_json", "read_json"]
