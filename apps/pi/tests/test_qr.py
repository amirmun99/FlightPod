"""Tests for flightpaper.display.qr."""

from __future__ import annotations

import pytest

from flightpaper.display.qr import QrRenderError, TARGET_MAX_PX, render_qr_image
from flightpaper.security.pairing import build_pair_uri


def test_renders_one_bit_image_at_target_size() -> None:
    img = render_qr_image("flightpaper://pair?p=abc", target_px=96)
    assert img.size == (96, 96)
    assert img.mode == "1"


def test_smaller_target_still_returns_target_size() -> None:
    img = render_qr_image("hi", target_px=48)
    assert img.size == (48, 48)


def test_default_target() -> None:
    img = render_qr_image("flightpaper://pair?p=" + "A" * 64)
    assert img.size == (TARGET_MAX_PX, TARGET_MAX_PX)


def test_pairing_uri_renders() -> None:
    payload = {
        "v": 1,
        "host": "172.20.10.4",
        "port": 8080,
        "device_id": "fp_aabbccdd",
        "device_name": "FlightPaper",
        "device_pub": "A" * 43,
        "pairing_secret": "B" * 43,
        "expires_at": 1_700_000_600,
        "code": "123-456",
    }
    uri = build_pair_uri(payload)
    img = render_qr_image(uri, target_px=96)
    assert img.size == (96, 96)


def test_oversized_payload_raises() -> None:
    # Force a payload large enough that the raw QR exceeds the target.
    huge = "X" * 5000
    with pytest.raises(QrRenderError):
        render_qr_image(huge, target_px=24)


def test_empty_text_rejected() -> None:
    with pytest.raises(QrRenderError):
        render_qr_image("")
