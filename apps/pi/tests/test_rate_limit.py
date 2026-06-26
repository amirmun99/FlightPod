"""Tests for flightpaper.opensky.rate_limit.RateLimiter."""

from __future__ import annotations

import random

from flightpaper.opensky.rate_limit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_initial_request_allowed() -> None:
    clock = Clock()
    rl = RateLimiter(min_interval_s=20.0, time_fn=clock)
    assert rl.can_request_now()


def test_min_interval_after_success() -> None:
    clock = Clock()
    rl = RateLimiter(min_interval_s=20.0, time_fn=clock)
    rl.on_success(rate_limit_remaining=42)
    assert rl.rate_limit_remaining == 42
    assert not rl.can_request_now()
    assert abs(rl.seconds_until_next_allowed() - 20.0) < 1e-6

    clock.advance(10)
    assert not rl.can_request_now()
    clock.advance(11)
    assert rl.can_request_now()


def test_backoff_respects_retry_after() -> None:
    clock = Clock()
    rl = RateLimiter(min_interval_s=10.0, time_fn=clock)
    delay = rl.on_rate_limited(retry_after_s=45.0)
    assert delay == 45.0
    clock.advance(30)
    assert not rl.can_request_now()
    clock.advance(20)
    assert rl.can_request_now()


def test_exponential_backoff_without_retry_after() -> None:
    random.seed(0)
    clock = Clock()
    rl = RateLimiter(min_interval_s=10.0, time_fn=clock, backoff_initial_s=5.0)

    d1 = rl.on_rate_limited()  # First retry: 5-second window (with full jitter).
    assert 2.5 <= d1 <= 5.0

    clock.advance(d1 + 0.01)
    d2 = rl.on_rate_limited()  # Doubles to 10.
    assert 5.0 <= d2 <= 10.0

    clock.advance(d2 + 0.01)
    d3 = rl.on_rate_limited()  # Doubles to 20.
    assert 10.0 <= d3 <= 20.0


def test_backoff_resets_on_success() -> None:
    random.seed(1)
    clock = Clock()
    rl = RateLimiter(min_interval_s=10.0, time_fn=clock, backoff_initial_s=5.0)

    rl.on_rate_limited()
    rl.on_rate_limited()
    clock.advance(100)
    rl.on_success()

    # New error should restart from backoff_initial.
    d = rl.on_rate_limited()
    assert d <= 5.0


def test_backoff_max_cap() -> None:
    random.seed(2)
    clock = Clock()
    rl = RateLimiter(
        min_interval_s=10.0,
        time_fn=clock,
        backoff_initial_s=10.0,
        backoff_max_s=20.0,
    )
    rl.on_rate_limited()        # 10
    clock.advance(100)
    rl.on_rate_limited()        # 20
    clock.advance(100)
    delay = rl.on_rate_limited()  # would be 40, capped to 20
    assert delay <= 20.0


def test_network_error_uses_same_backoff() -> None:
    clock = Clock()
    rl = RateLimiter(min_interval_s=10.0, time_fn=clock, backoff_initial_s=5.0)
    d = rl.on_network_error()
    assert d > 0
    assert not rl.can_request_now()
