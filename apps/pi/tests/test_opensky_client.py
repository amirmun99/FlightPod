"""Tests for OpenSkyClient + OpenSkyProvider using httpx.MockTransport."""

from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest

from flightpaper.opensky.client import (
    OpenSkyClient,
    OpenSkyError,
    OpenSkyRateLimited,
)
from flightpaper.opensky.provider import OpenSkyProvider
from flightpaper.opensky.rate_limit import RateLimiter
from flightpaper.utils.geo import latlon_bbox


# A canonical OpenSky state vector. icao24 plus the standard 17 positional fields.
_NOW = 1_700_000_000


def _ok_response(states: list[list[object]] | None = None) -> httpx.Response:
    body = {
        "time": _NOW,
        "states": states
        or [
            [
                "ac0001",
                "ACA123  ",
                "Canada",
                _NOW - 5,
                _NOW - 5,
                -79.81,
                43.33,
                9525.0,
                False,
                240.0,
                82.0,
                0.0,
                None,
                9540.0,
                "1234",
                False,
                0,
            ]
        ],
    }
    return httpx.Response(
        200,
        content=json.dumps(body),
        headers={"X-Rate-Limit-Remaining": "42", "Content-Type": "application/json"},
    )


def _make_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_anonymous_request_includes_bbox_params() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok_response()

    client = OpenSkyClient(
        base_url="https://example.test/api",
        transport=_make_transport(handler),
    )
    bbox = latlon_bbox(43.3255, -79.7990, 25.0)
    response = client.fetch_states(bbox=bbox)

    assert response.http_status == 200
    assert response.states.count == 1
    assert response.rate_limit_remaining == 42

    assert len(seen) == 1
    req = seen[0]
    assert req.url.path.endswith("/states/all")
    qs = dict(req.url.params)
    assert qs["lamin"]
    assert qs["lomin"]
    assert qs["lamax"]
    assert qs["lomax"]
    # No Authorization header in anonymous mode.
    assert "Authorization" not in req.headers
    client.close()


def test_extended_flag_propagates() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok_response()

    client = OpenSkyClient(
        base_url="https://example.test/api",
        transport=_make_transport(handler),
    )
    bbox = latlon_bbox(43.3255, -79.7990, 25.0)
    client.fetch_states(bbox=bbox, extended=True)

    assert dict(seen[0].url.params).get("extended") == "1"
    client.close()


def test_429_raises_rate_limited_with_retry_after() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            content='{"detail":"rate limited"}',
            headers={"Retry-After": "12"},
        )

    client = OpenSkyClient(
        base_url="https://example.test/api",
        transport=_make_transport(handler),
    )
    with pytest.raises(OpenSkyRateLimited) as exc_info:
        client.fetch_states(bbox=latlon_bbox(0, 0, 1))
    assert exc_info.value.retry_after_s == 12.0
    client.close()


def test_5xx_raises_opensky_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content="boom")

    client = OpenSkyClient(
        base_url="https://example.test/api",
        transport=_make_transport(handler),
    )
    with pytest.raises(OpenSkyError):
        client.fetch_states(bbox=latlon_bbox(0, 0, 1))
    client.close()


def test_network_error_raises_opensky_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = OpenSkyClient(
        base_url="https://example.test/api",
        transport=_make_transport(handler),
    )
    with pytest.raises(OpenSkyError):
        client.fetch_states(bbox=latlon_bbox(0, 0, 1))
    client.close()


def test_authenticated_mode_attaches_bearer_token() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "openid-connect/token" in str(request.url):
            return httpx.Response(
                200,
                content=json.dumps({"access_token": "tok-123", "expires_in": 3600}),
            )
        return _ok_response()

    client = OpenSkyClient(
        base_url="https://example.test/api",
        client_id="cid",
        client_secret="csec",
        transport=_make_transport(handler),
    )
    assert client.authenticated
    response = client.fetch_states(bbox=latlon_bbox(0, 0, 1))
    assert response.http_status == 200

    # First call hits token endpoint, second hits /states/all with bearer.
    assert any("openid-connect/token" in str(r.url) for r in seen)
    states_req = next(r for r in seen if r.url.path.endswith("/states/all"))
    assert states_req.headers.get("Authorization") == "Bearer tok-123"

    # Second fetch reuses the cached token (no additional token request).
    seen.clear()
    client.fetch_states(bbox=latlon_bbox(0, 0, 1))
    assert all("openid-connect/token" not in str(r.url) for r in seen)
    client.close()


# ---------------------------------------------------------------------------
# Provider behavior
# ---------------------------------------------------------------------------


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_provider_caches_last_good_states_through_outage() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _ok_response()
        return httpx.Response(500, content="boom")

    client = OpenSkyClient(
        base_url="https://example.test/api",
        transport=_make_transport(handler),
    )
    clock = _Clock()
    limiter = RateLimiter(min_interval_s=0.0, time_fn=clock)
    provider = OpenSkyProvider(client=client, limiter=limiter, cache_ttl_seconds=60)
    bbox = latlon_bbox(43.3255, -79.7990, 25.0)

    fresh = provider.fetch(bbox=bbox)
    assert fresh.count == 1
    assert provider.status.last_status == "ok"

    # Outage: server returns 500.
    clock.advance(1)
    cached = provider.fetch(bbox=bbox)
    assert cached.count == 1  # same as cached
    assert provider.status.last_status == "error"
    client.close()


def test_provider_marks_stale_after_ttl() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _ok_response()

    client = OpenSkyClient(
        base_url="https://example.test/api",
        transport=_make_transport(handler),
    )
    clock = _Clock()
    limiter = RateLimiter(min_interval_s=600.0, time_fn=clock)
    provider = OpenSkyProvider(client=client, limiter=limiter, cache_ttl_seconds=10)
    bbox = latlon_bbox(0, 0, 1)

    provider.fetch(bbox=bbox)
    # Force backoff: limiter prevents another call. Cache is now > TTL old.
    clock.advance(30)
    states = provider.fetch(bbox=bbox)  # returns cached, sets stale
    assert states.count == 1
    assert provider.status.last_status == "stale"
    client.close()


def test_provider_rate_limited_status() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, content="rate limited", headers={"Retry-After": "5"})

    client = OpenSkyClient(
        base_url="https://example.test/api",
        transport=_make_transport(handler),
    )
    clock = _Clock()
    limiter = RateLimiter(min_interval_s=0.0, time_fn=clock)
    provider = OpenSkyProvider(client=client, limiter=limiter)
    bbox = latlon_bbox(0, 0, 1)

    states = provider.fetch(bbox=bbox)
    assert states.count == 0
    assert provider.status.last_status == "rate_limited"
    client.close()
