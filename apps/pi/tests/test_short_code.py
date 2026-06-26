"""Tests for flightpaper.security.tokens.derive_short_code."""

from __future__ import annotations

import re

import pytest

from flightpaper.security.tokens import derive_short_code


def test_format_is_xxx_dash_xxx() -> None:
    code = derive_short_code(b"\x42" * 32)
    assert re.fullmatch(r"\d{3}-\d{3}", code)


def test_deterministic() -> None:
    secret = b"some-32-byte-secret-padding-yes!"
    assert derive_short_code(secret) == derive_short_code(secret)


def test_different_secrets_diverge() -> None:
    a = derive_short_code(b"\x00" * 32)
    b = derive_short_code(b"\x01" * 32)
    assert a != b


def test_empty_secret_rejected() -> None:
    with pytest.raises(ValueError):
        derive_short_code(b"")
