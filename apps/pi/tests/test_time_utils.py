"""Tests for flightpaper.utils.time_utils."""

from __future__ import annotations

from flightpaper.utils.time_utils import (
    age_seconds,
    format_age,
    is_expired,
    is_fresh,
    is_stale,
)


def test_age_seconds_with_explicit_now() -> None:
    assert age_seconds(100, now=160) == 60
    assert age_seconds(0, now=0) == 0
    # Future timestamps clamp to zero.
    assert age_seconds(200, now=100) == 0


def test_age_seconds_none() -> None:
    assert age_seconds(None) is None


def test_freshness_thresholds() -> None:
    # 30 s old, threshold 60 s → fresh.
    assert is_fresh(100, threshold_s=60, now=130) is True
    # 90 s old, threshold 60 s → not fresh.
    assert is_fresh(100, threshold_s=60, now=190) is False
    # None timestamp → never fresh.
    assert is_fresh(None, threshold_s=60, now=130) is False


def test_stale_thresholds() -> None:
    # 100 s old, warning 60 s → stale.
    assert is_stale(0, warning_s=60, now=100) is True
    # 30 s old, warning 60 s → not stale.
    assert is_stale(0, warning_s=60, now=30) is False
    # None → not "stale", it's missing.
    assert is_stale(None, warning_s=60, now=100) is False


def test_expired_thresholds() -> None:
    assert is_expired(0, expired_s=60, now=100) is True
    assert is_expired(0, expired_s=60, now=30) is False
    # Missing timestamp is treated as expired.
    assert is_expired(None, expired_s=60, now=100) is True


def test_format_age_buckets() -> None:
    assert format_age(None) == "--"
    assert format_age(0) == "0s"
    assert format_age(45) == "45s"
    assert format_age(60) == "1m"
    assert format_age(180) == "3m"
    assert format_age(3600) == "1h"
    assert format_age(7200) == "2h"
    assert format_age(86400) == "1d"
    assert format_age(2 * 86400) == "2d"
