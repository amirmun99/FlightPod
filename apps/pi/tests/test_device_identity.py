"""Tests for flightpaper.security.device_identity."""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path

import pytest

from flightpaper.security.device_identity import (
    create_identity,
    load_identity,
    load_or_create_identity,
)


_DEVICE_ID_RE = re.compile(r"^fp_[0-9a-f]{8}$")


def test_create_identity_generates_canonical_fields(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, device_name="Custom")
    assert _DEVICE_ID_RE.fullmatch(identity.device_id)
    assert identity.device_name == "Custom"
    assert len(identity.private_key) == 32
    assert len(identity.public_key) == 32
    assert identity.created_at > 0


def test_persisted_file_is_secure(tmp_path: Path) -> None:
    create_identity(tmp_path, device_name="A")
    path = tmp_path / "device_identity.json"
    assert path.exists()
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_round_trip_load(tmp_path: Path) -> None:
    original = create_identity(tmp_path, device_name="Test")
    loaded = load_identity(tmp_path)
    assert loaded == original


def test_load_or_create_reuses_existing(tmp_path: Path) -> None:
    first = load_or_create_identity(tmp_path)
    second = load_or_create_identity(tmp_path)
    assert first == second


def test_load_or_create_creates_when_missing(tmp_path: Path) -> None:
    sub = tmp_path / "secure"
    identity = load_or_create_identity(sub, device_name="Fresh")
    assert (sub / "device_identity.json").exists()
    assert identity.device_name == "Fresh"


def test_corrupt_device_id_rejected(tmp_path: Path) -> None:
    create_identity(tmp_path)
    raw = json.loads((tmp_path / "device_identity.json").read_text())
    raw["device_id"] = "bad"
    (tmp_path / "device_identity.json").write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_identity(tmp_path)
