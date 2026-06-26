"""Background coroutines started by the FastAPI lifespan.

Three loops:

* :func:`opensky_poll_loop` — drives :meth:`OpenSkyProvider.fetch` on the
  configured cadence, feeds the result through the aircraft pipeline, and
  publishes the enriched list onto ``AppState.last_aircraft``.
* :func:`display_refresh_loop` — renders the current page via Pillow and
  pushes it to the active ePaper driver (Null driver on macOS dev).
* :func:`battery_poll_loop` — samples PiSugar via the battery provider
  and parks the result on ``AppState.battery_status``.
"""

from __future__ import annotations

import asyncio
import logging
import time

from ..aircraft.filters import FilterConfig
from ..aircraft.processor import UserPosition, process_states
from ..display.epaper import EPaperDriver, make_driver
from ..display.renderer import render_page
from ..opensky.client import OpenSkyError
from ..utils.geo import latlon_bbox
from ..utils.time_utils import now_ts
from .app_state import AppState

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenSky polling
# ---------------------------------------------------------------------------


def _current_interval(state: AppState) -> float:
    """Pick polling interval based on battery-saver state (not yet wired)."""

    cfg = state.config.opensky
    # Phase 6 will plug in battery info; for now use the normal interval.
    return float(cfg.update_interval_seconds)


async def opensky_poll_loop(state: AppState) -> None:
    """Continuously poll OpenSky for the bbox around the current location."""

    log.info("opensky poll loop started")
    while not state.stop_event.is_set():
        try:
            interval = _current_interval(state)
            location = state.location.usable_for_polling()
            force = state.force_poll
            state.force_poll = False

            if location is None:
                log.debug("no usable location; skipping poll")
                await _sleep_or_stop(state, 5.0)
                continue

            radius_km = float(state.config.ui.radius_km)
            bbox = latlon_bbox(location.lat, location.lon, radius_km)
            cfg = FilterConfig(
                include_ground_aircraft=state.config.opensky.include_ground_aircraft,
                max_age_seconds=int(state.config.opensky.max_aircraft_age_seconds),
                radius_km=radius_km,
            )
            user = UserPosition(lat=location.lat, lon=location.lon)

            try:
                # The sync httpx client runs in a thread so we don't block
                # the event loop on a slow network.
                opensky_states = await asyncio.to_thread(
                    state.opensky_provider.fetch, bbox=bbox
                )
            except OpenSkyError as exc:
                log.warning("opensky poll error: %s", exc)
                opensky_states = state.opensky_provider.cached_states()
                if opensky_states is None:
                    await _sleep_or_stop(state, interval)
                    continue

            enriched = process_states(
                opensky_states,
                user=user,
                config=cfg,
                now_ts=now_ts(),
            )
            state.last_aircraft = enriched
            state.last_aircraft_at = time.time()
            state.force_refresh = True

            log.debug(
                "poll cycle: %d aircraft within %.0f km",
                len(enriched),
                radius_km,
            )

            if force:
                # When forced, we still respect ``min_interval_seconds``
                # implicitly via RateLimiter on the provider.
                await _sleep_or_stop(state, 1.0)
            else:
                await _sleep_or_stop(state, interval)

        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - loop must never die
            log.exception("opensky poll loop tick failed; backing off 10s")
            await _sleep_or_stop(state, 10.0)

    log.info("opensky poll loop exited")


# ---------------------------------------------------------------------------
# Display refresh
# ---------------------------------------------------------------------------


async def display_refresh_loop(
    state: AppState,
    *,
    driver: EPaperDriver | None = None,
) -> None:
    """Render the current page and push it to the ePaper driver.

    Refresh strategy (spec §19):

    * Full refresh on init, page change, every ``full_refresh_every`` partials,
      and whenever ``partial_refresh`` is disabled.
    * Partial refresh otherwise.
    """

    if driver is None:
        driver = make_driver(
            state.config.display.driver,
            width=int(state.config.display.width),
            height=int(state.config.display.height),
            rotation=int(state.config.display.rotation),
        )

    try:
        await asyncio.to_thread(driver.init)
    except Exception:  # noqa: BLE001
        log.exception("display driver init failed")
        return

    log.info("display refresh loop started (driver=%s)", driver.__class__.__name__)
    interval = max(2.0, float(state.config.opensky.update_interval_seconds) / 2.0)

    partial_count = 0
    last_page = state.current_page

    try:
        while not state.stop_event.is_set():
            try:
                should_refresh = state.force_refresh or last_page != state.current_page
                if not should_refresh:
                    await _sleep_or_stop(state, interval)
                    continue

                state.force_refresh = False
                page_changed = state.current_page != last_page
                last_page = state.current_page

                image = await asyncio.to_thread(render_page, state)

                use_full = (
                    page_changed
                    or not state.config.display.partial_refresh
                    or partial_count >= int(state.config.display.full_refresh_every)
                )
                if use_full:
                    await asyncio.to_thread(driver.display_full, image)
                    partial_count = 0
                    log.debug("display: full refresh, page=%s", last_page)
                else:
                    await asyncio.to_thread(driver.display_partial, image)
                    partial_count += 1
                    log.debug(
                        "display: partial refresh, page=%s (#%d)",
                        last_page,
                        partial_count,
                    )

                state.last_refresh_at = time.time()
                await _sleep_or_stop(state, interval)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - loop must never die
                log.exception("display refresh tick failed; backing off 5s")
                await _sleep_or_stop(state, 5.0)
    finally:
        try:
            await asyncio.to_thread(driver.sleep)
            await asyncio.to_thread(driver.cleanup)
        except Exception:  # noqa: BLE001
            log.exception("driver shutdown failed")
        log.info("display refresh loop exited")


# ---------------------------------------------------------------------------
# Battery polling
# ---------------------------------------------------------------------------


async def battery_poll_loop(state: AppState, *, interval_s: float = 15.0) -> None:
    """Periodically sample battery state via the provider."""

    log.info("battery poll loop started")
    while not state.stop_event.is_set():
        try:
            status = await asyncio.to_thread(state.battery_provider.read)
            state.battery_status = status
            await _sleep_or_stop(state, interval_s)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("battery poll failed; backing off 30s")
            await _sleep_or_stop(state, 30.0)
    log.info("battery poll loop exited")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _sleep_or_stop(state: AppState, seconds: float) -> None:
    """Await ``seconds`` but wake early if shutdown is requested."""

    try:
        await asyncio.wait_for(state.stop_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        return


__all__ = ["display_refresh_loop", "opensky_poll_loop"]
