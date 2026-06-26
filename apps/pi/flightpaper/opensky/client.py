"""HTTP client for the OpenSky Network ``/states/all`` endpoint.

The client supports:

* Anonymous polling (no auth headers).
* OAuth2 ``client_credentials`` against the OpenSky Keycloak realm when
  ``OPENSKY_CLIENT_ID`` and ``OPENSKY_CLIENT_SECRET`` are present.
* Bounding-box queries (lamin, lomin, lamax, lomax) per spec §13.
* A configurable timeout and an injectable transport for testing.

The client deliberately does *not* manage retries or rate-limit backoff —
the higher-level :class:`OpenSkyProvider` owns that policy via
:class:`flightpaper.opensky.rate_limit.RateLimiter`.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from ..utils.geo import BoundingBox
from .models import OpenSkyStates
from .parser import parse_states_response

log = logging.getLogger(__name__)


# OpenSky migrated to OAuth2 client_credentials. Token endpoint:
_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol"
    "/openid-connect/token"
)
_TOKEN_REFRESH_MARGIN_S = 60


class OpenSkyError(Exception):
    """Base class for OpenSky transport errors."""


class OpenSkyRateLimited(OpenSkyError):
    def __init__(self, *, retry_after_s: float | None = None) -> None:
        super().__init__("opensky rate limited")
        self.retry_after_s = retry_after_s


class OpenSkyAuthError(OpenSkyError):
    """Authentication against the token endpoint failed."""


@dataclass
class OpenSkyResponse:
    """Public envelope returned by :meth:`OpenSkyClient.fetch_states`."""

    states: OpenSkyStates
    http_status: int
    rate_limit_remaining: int | None


class OpenSkyClient:
    """Synchronous OpenSky REST client.

    Parameters
    ----------
    base_url:
        OpenSky API base, e.g. ``https://opensky-network.org/api``. Trailing
        slashes are stripped.
    timeout_s:
        Per-request timeout in seconds.
    client_id, client_secret:
        OAuth2 credentials. If either is missing, the client runs
        anonymously.
    transport:
        Optional httpx transport; pass ``httpx.MockTransport`` in tests.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_s: float = 8.0,
        client_id: str | None = None,
        client_secret: str | None = None,
        transport: httpx.BaseTransport | None = None,
        user_agent: str = "FlightPaper/0.1.0",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._client_id = client_id or os.environ.get("OPENSKY_CLIENT_ID") or None
        self._client_secret = client_secret or os.environ.get("OPENSKY_CLIENT_SECRET") or None
        self._user_agent = user_agent
        self._transport = transport

        self._http = httpx.Client(
            timeout=timeout_s,
            transport=transport,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

        self._token: str | None = None
        self._token_expiry: float = 0.0

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OpenSkyClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def authenticated(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def fetch_states(
        self,
        *,
        bbox: BoundingBox,
        extended: bool = False,
    ) -> OpenSkyResponse:
        """Call ``/states/all`` and return parsed aircraft.

        Raises
        ------
        OpenSkyRateLimited
            On HTTP 429. Carries ``Retry-After`` when present.
        OpenSkyError
            On other transport errors (network, non-2xx).
        """

        params: dict[str, Any] = {
            "lamin": bbox.lamin,
            "lomin": bbox.lomin,
            "lamax": bbox.lamax,
            "lomax": bbox.lomax,
        }
        if extended:
            params["extended"] = 1

        headers: dict[str, str] = {}
        if self.authenticated:
            token = self._ensure_token()
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = self._http.get(
                f"{self._base_url}/states/all",
                params=params,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            log.warning("opensky network error: %s", exc.__class__.__name__)
            raise OpenSkyError(f"opensky network error: {exc}") from exc

        if response.status_code == 429:
            retry_after = _parse_retry_after(response.headers)
            raise OpenSkyRateLimited(retry_after_s=retry_after)

        if response.status_code >= 400:
            raise OpenSkyError(
                f"opensky http {response.status_code}: {response.text[:200]}"
            )

        rate_remaining = _parse_int_header(response.headers, "X-Rate-Limit-Remaining")
        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenSkyError(f"opensky: invalid JSON: {exc}") from exc

        states = parse_states_response(payload)
        states.rate_limit_remaining = rate_remaining
        return OpenSkyResponse(
            states=states,
            http_status=response.status_code,
            rate_limit_remaining=rate_remaining,
        )

    # ------------------------------------------------------------------
    # OAuth2 client_credentials
    # ------------------------------------------------------------------

    def _ensure_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - _TOKEN_REFRESH_MARGIN_S:
            return self._token

        assert self._client_id and self._client_secret
        try:
            response = self._http.post(
                _TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as exc:
            raise OpenSkyAuthError(f"token request failed: {exc}") from exc

        if response.status_code >= 400:
            raise OpenSkyAuthError(
                f"token endpoint returned {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise OpenSkyAuthError(f"token endpoint invalid JSON: {exc}") from exc

        token = body.get("access_token")
        if not token:
            raise OpenSkyAuthError("token endpoint did not return access_token")

        expires_in = float(body.get("expires_in") or 300)
        self._token = token
        self._token_expiry = now + expires_in
        return token


def _parse_int_header(headers: Mapping[str, str], name: str) -> int | None:
    raw = headers.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_retry_after(headers: Mapping[str, str]) -> float | None:
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


__all__ = [
    "OpenSkyAuthError",
    "OpenSkyClient",
    "OpenSkyError",
    "OpenSkyRateLimited",
    "OpenSkyResponse",
]
