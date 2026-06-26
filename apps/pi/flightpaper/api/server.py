"""FastAPI app + lifespan that wires AppState, routes, and background tasks.

Run with:

    uvicorn flightpaper.api.server:app --host 0.0.0.0 --port 8080

Or via the packaged entrypoint:

    python -m flightpaper.main
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ..logging_setup import setup_logging
from .app_state import AppState, build_app_state
from .background import (
    battery_poll_loop,
    display_refresh_loop,
    opensky_poll_loop,
)
from .routes_public import router as public_router
from .routes_secure import router as secure_router
from .schemas import error_dict

log = logging.getLogger(__name__)


def create_app(
    *,
    state: AppState | None = None,
    start_background_tasks: bool = True,
) -> FastAPI:
    """Build the FastAPI app.

    Parameters
    ----------
    state:
        Pre-built :class:`AppState`. When omitted, the lifespan calls
        :func:`build_app_state` itself. Tests pass in a custom state.
    start_background_tasks:
        Set ``False`` in tests that don't want the OpenSky / refresh
        loops to fire (the TestClient still exercises route handlers).
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log_dir = setup_logging(
            level=(state.config.app.log_level if state else "INFO"),
        )
        log.info("flightpaper api: log dir=%s", log_dir)

        resolved_state = state if state is not None else build_app_state()
        app.state.flightpaper = resolved_state

        tasks: list[asyncio.Task] = []
        if start_background_tasks:
            poller = asyncio.create_task(
                opensky_poll_loop(resolved_state), name="opensky_poller"
            )
            refresher = asyncio.create_task(
                display_refresh_loop(resolved_state), name="display_refresh"
            )
            battery = asyncio.create_task(
                battery_poll_loop(resolved_state), name="battery_poller"
            )
            resolved_state.poller_task = poller
            resolved_state.refresh_task = refresher
            tasks.extend((poller, refresher, battery))

        try:
            yield
        finally:
            resolved_state.stop_event.set()
            for t in tasks:
                t.cancel()
            for t in tasks:
                try:
                    await t
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
            resolved_state.opensky_client.close()

    app = FastAPI(
        title="FlightPaper",
        version=os.environ.get("FLIGHTPAPER_VERSION", "0.1.0"),
        lifespan=lifespan,
        docs_url=None,           # We don't ship docs / OpenAPI publicly.
        redoc_url=None,
        openapi_url=None,
    )

    app.include_router(public_router)
    app.include_router(secure_router)

    # ----- Error handlers: keep response bodies opaque ---------------------

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        # HTTPException.detail is already an error dict in our code.
        detail = exc.detail
        if not isinstance(detail, dict) or "error" not in detail:
            detail = error_dict(str(detail) if isinstance(detail, str) else "internal")
        return JSONResponse(detail, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled exception in request: %s", exc)
        return JSONResponse(error_dict("internal", "internal server error"), status_code=500)

    return app


# Default ASGI app used by ``uvicorn flightpaper.api.server:app``.
app = create_app()


__all__ = ["app", "create_app"]
