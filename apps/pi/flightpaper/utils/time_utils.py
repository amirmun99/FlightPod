"""Time helpers. Pi side uses UNIX seconds throughout for simplicity."""

from __future__ import annotations

import time
from typing import Callable


def now_ts() -> int:
    """Current UNIX timestamp in seconds (int)."""

    return int(time.time())


def now_ts_float() -> float:
    """Sub-second timestamp; for refresh-loop pacing."""

    return time.time()


def age_seconds(ts: int | float | None, *, now: int | None = None) -> int | None:
    """Seconds elapsed since ``ts``; ``None`` if input is ``None``."""

    if ts is None:
        return None
    n = now if now is not None else now_ts()
    return max(0, int(n - ts))


def is_fresh(ts: int | None, *, threshold_s: int, now: int | None = None) -> bool:
    age = age_seconds(ts, now=now)
    return age is not None and age <= threshold_s


def is_stale(ts: int | None, *, warning_s: int, now: int | None = None) -> bool:
    age = age_seconds(ts, now=now)
    return age is not None and age > warning_s


def is_expired(ts: int | None, *, expired_s: int, now: int | None = None) -> bool:
    age = age_seconds(ts, now=now)
    return age is None or age > expired_s


def format_age(age_s: int | None) -> str:
    """Human-friendly compact age string for the status bar (e.g. ``14s``, ``3m``, ``--``)."""

    if age_s is None:
        return "--"
    if age_s < 60:
        return f"{age_s}s"
    if age_s < 3600:
        return f"{age_s // 60}m"
    if age_s < 86400:
        return f"{age_s // 3600}h"
    return f"{age_s // 86400}d"


__all__ = [
    "now_ts",
    "now_ts_float",
    "age_seconds",
    "is_fresh",
    "is_stale",
    "is_expired",
    "format_age",
]
