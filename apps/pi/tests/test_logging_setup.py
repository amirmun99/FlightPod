"""Tests for flightpaper.logging_setup."""

from __future__ import annotations

import logging
from pathlib import Path

from flightpaper.logging_setup import RedactingFilter, setup_logging


def _make_record(msg: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_redacts_pairing_secret() -> None:
    f = RedactingFilter()
    rec = _make_record("computed pairing_secret=hunter2 and proceeded")
    assert f.filter(rec) is True
    assert "hunter2" not in rec.getMessage()
    assert "pairing_secret" in rec.getMessage()


def test_redacts_session_key_json_form() -> None:
    f = RedactingFilter()
    rec = _make_record('{"session_key": "abcdef0123456789", "ok": true}')
    f.filter(rec)
    assert "abcdef0123456789" not in rec.getMessage()


def test_redacts_wifi_password() -> None:
    f = RedactingFilter()
    rec = _make_record("connecting with wifi_password=correct-horse-battery-staple")
    f.filter(rec)
    assert "correct-horse-battery-staple" not in rec.getMessage()


def test_passes_through_unrelated_messages() -> None:
    f = RedactingFilter()
    rec = _make_record("Pi booted, ip=172.20.10.4, aircraft=7")
    f.filter(rec)
    assert "172.20.10.4" in rec.getMessage()


def test_setup_logging_writes_to_log_dir(tmp_path: Path) -> None:
    setup_logging(level="DEBUG", log_dir=tmp_path)
    logging.getLogger("flightpaper.test").info("boot complete; pairing_secret=topsecret123")
    log_file = tmp_path / "flightpaper.log"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "boot complete" in contents
    assert "topsecret123" not in contents
    assert "pairing_secret=***" in contents
