"""Logging configuration for the FlightPaper Pi service.

Two handlers by default: a rotating file handler (production, under
``/var/log/flightpaper/``) and a stderr handler (development and systemd
capture). A redaction filter strips known secret keys from every record
before formatting.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
from pathlib import Path

# Substrings we redact from any logged value. Matching is case-insensitive
# and operates on the formatted message body. The Pi service should never
# pass these through ``logger.info(...)`` directly anyway; this is defense
# in depth in case a third-party library leaks one.
_REDACTED_KEYS: tuple[str, ...] = (
    "pairing_secret",
    "session_key",
    "session_keys",
    "opensky_client_secret",
    "wifi_password",
    "psk",
    "passphrase",
)

# Catch "<key>=<value>" and "<key>: <value>" plus JSON forms (which have a
# closing quote between key and separator); replace the value with "***".
_KV_PATTERN = re.compile(
    r"(?P<key>(?:%s))(?P<sep>['\"]?\s*[:=]\s*['\"]?)(?P<val>[^\s'\",}]+)"
    % "|".join(_REDACTED_KEYS),
    re.IGNORECASE,
)


class RedactingFilter(logging.Filter):
    """Replace values associated with sensitive keys in log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - logging must never raise
            return True
        redacted = _KV_PATTERN.sub(
            lambda m: f"{m.group('key')}{m.group('sep')}***",
            message,
        )
        if redacted != message:
            # Replace the resolved message and clear args so handlers don't
            # re-substitute the original args.
            record.msg = redacted
            record.args = ()
        return True


_DEFAULT_LOG_DIR = Path("/var/log/flightpaper")
_DEV_LOG_DIR = Path(os.path.expanduser("~/.flightpaper/logs"))


def _pick_log_dir() -> Path:
    """Return a writable log directory, preferring the production location."""

    if os.environ.get("FLIGHTPAPER_DEV") == "1":
        return _DEV_LOG_DIR

    try:
        _DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        # Sanity-check writability.
        probe = _DEFAULT_LOG_DIR / ".write_probe"
        probe.touch()
        probe.unlink(missing_ok=True)
        return _DEFAULT_LOG_DIR
    except (PermissionError, OSError):
        _DEV_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return _DEV_LOG_DIR


def setup_logging(level: str = "INFO", *, log_dir: Path | None = None) -> Path:
    """Wire up FlightPaper logging.

    Returns the directory where log files are written, for the caller to log
    once at startup.
    """

    resolved_dir = log_dir or _pick_log_dir()
    resolved_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level.upper())

    # Tear down anything from previous calls (tests, reloads).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    redactor = RedactingFilter()

    file_handler = logging.handlers.RotatingFileHandler(
        resolved_dir / "flightpaper.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(redactor)
    root.addHandler(file_handler)

    err_handler = logging.handlers.RotatingFileHandler(
        resolved_dir / "flightpaper.err",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    err_handler.setLevel(logging.WARNING)
    err_handler.setFormatter(fmt)
    err_handler.addFilter(redactor)
    root.addHandler(err_handler)

    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(fmt)
    stderr_handler.addFilter(redactor)
    root.addHandler(stderr_handler)

    return resolved_dir


__all__ = ["setup_logging", "RedactingFilter"]
