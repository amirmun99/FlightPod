"""Tests for flightpaper.location.manager.LocationManager."""

from __future__ import annotations

import pytest

from flightpaper.location.manager import LocationManager
from flightpaper.location.manual_provider import ManualProvider
from flightpaper.location.models import Freshness, LocationPayload
from flightpaper.location.phone_provider import PhoneProvider


class Clock:
    def __init__(self, t: int = 1_700_000_000) -> None:
        self.t = t

    def __call__(self) -> int:
        return self.t

    def advance(self, dt: int) -> None:
        self.t += dt


def _payload(*, ts: int, lat: float = 43.3255, lon: float = -79.7990) -> LocationPayload:
    return LocationPayload(
        lat=lat,
        lon=lon,
        accuracy_m=8.0,
        altitude_m=120.0,
        heading_deg=52.0,
        speed_mps=1.4,
        source="iphone_background",
        timestamp=ts,
    )


# ---------------------------------------------------------------------------
# Empty manager
# ---------------------------------------------------------------------------


def test_empty_manager_has_no_location() -> None:
    clock = Clock()
    mgr = LocationManager(phone=PhoneProvider(), time_fn=clock)
    assert mgr.current() is None
    assert mgr.age_seconds() is None
    assert mgr.freshness() == Freshness.NONE
    assert mgr.usable_for_polling() is None

    status = mgr.status_dict()
    assert status["source"] is None
    assert status["fresh"] is False
    assert status["state"] == "none"


# ---------------------------------------------------------------------------
# Phone payload acceptance + freshness transitions
# ---------------------------------------------------------------------------


def test_accept_and_query_phone_payload() -> None:
    clock = Clock()
    phone = PhoneProvider()
    mgr = LocationManager(
        phone=phone,
        stale_warning_seconds=900,
        expired_seconds=3600,
        time_fn=clock,
    )

    mgr.apply_phone_payload(_payload(ts=clock.t - 5), now=clock.t)
    loc = mgr.current()
    assert loc is not None
    assert loc.lat == 43.3255
    assert mgr.age_seconds() == 5
    assert mgr.freshness() == Freshness.FRESH
    assert mgr.usable_for_polling() is loc


def test_freshness_transitions_with_age() -> None:
    clock = Clock()
    phone = PhoneProvider()
    mgr = LocationManager(
        phone=phone,
        stale_warning_seconds=900,
        expired_seconds=3600,
        time_fn=clock,
    )
    mgr.apply_phone_payload(_payload(ts=clock.t), now=clock.t)

    clock.advance(100)
    assert mgr.freshness() == Freshness.FRESH
    assert mgr.usable_for_polling() is not None

    clock.advance(900)  # total 1000s
    assert mgr.freshness() == Freshness.STALE
    assert mgr.usable_for_polling() is not None  # stale is still usable

    clock.advance(3000)  # total 4000s, past expired
    assert mgr.freshness() == Freshness.EXPIRED
    assert mgr.usable_for_polling() is None


def test_status_dict_reflects_freshness() -> None:
    clock = Clock()
    mgr = LocationManager(phone=PhoneProvider(), time_fn=clock)
    mgr.apply_phone_payload(_payload(ts=clock.t - 10), now=clock.t)

    status = mgr.status_dict()
    assert status["source"] == "iphone_background"
    assert status["age_seconds"] == 10
    assert status["accuracy_m"] == 8.0
    assert status["fresh"] is True
    assert status["state"] == "fresh"

    clock.advance(1500)
    status = mgr.status_dict()
    assert status["fresh"] is False
    assert status["state"] == "stale"


def test_overwriting_payload_replaces_position() -> None:
    clock = Clock()
    mgr = LocationManager(phone=PhoneProvider(), time_fn=clock)
    mgr.apply_phone_payload(_payload(ts=clock.t, lat=43.0, lon=-79.0), now=clock.t)
    clock.advance(5)
    mgr.apply_phone_payload(_payload(ts=clock.t, lat=44.0, lon=-80.0), now=clock.t)

    loc = mgr.current()
    assert loc is not None and loc.lat == 44.0 and loc.lon == -80.0


# ---------------------------------------------------------------------------
# Manual fallback
# ---------------------------------------------------------------------------


def test_manual_used_when_phone_empty() -> None:
    clock = Clock()
    manual = ManualProvider(lat=43.0, lon=-79.0, label="Toronto", time_fn=clock)
    mgr = LocationManager(phone=PhoneProvider(), manual=manual, time_fn=clock)

    loc = mgr.current()
    assert loc is not None
    assert loc.lat == 43.0
    assert loc.source.startswith("manual:")
    # Manual is always-fresh.
    assert mgr.freshness() == Freshness.FRESH
    assert mgr.usable_for_polling() is not None


def test_phone_overrides_manual_by_default() -> None:
    clock = Clock()
    manual = ManualProvider(lat=43.0, lon=-79.0, label="Toronto", time_fn=clock)
    mgr = LocationManager(phone=PhoneProvider(), manual=manual, time_fn=clock)

    mgr.apply_phone_payload(_payload(ts=clock.t, lat=44.4, lon=-80.5), now=clock.t)
    loc = mgr.current()
    assert loc is not None and loc.lat == 44.4 and loc.source == "iphone_background"


def test_primary_manual_overrides_phone() -> None:
    clock = Clock()
    manual = ManualProvider(lat=43.0, lon=-79.0, label="Toronto", time_fn=clock)
    mgr = LocationManager(
        phone=PhoneProvider(),
        manual=manual,
        primary_source="manual",
        time_fn=clock,
    )

    mgr.apply_phone_payload(_payload(ts=clock.t, lat=44.4, lon=-80.5), now=clock.t)
    loc = mgr.current()
    assert loc is not None
    assert loc.lat == 43.0
    assert loc.source.startswith("manual:")


def test_disabled_manual_falls_back_to_phone() -> None:
    clock = Clock()
    manual = ManualProvider(
        lat=43.0, lon=-79.0, label="Toronto", enabled=False, time_fn=clock
    )
    mgr = LocationManager(phone=PhoneProvider(), manual=manual, time_fn=clock)
    assert mgr.current() is None

    mgr.apply_phone_payload(_payload(ts=clock.t), now=clock.t)
    assert mgr.current() is not None

    # Now enable manual and use primary=manual.
    manual.set_enabled(True)
    mgr.set_primary_source("manual")
    loc = mgr.current()
    assert loc is not None and loc.source.startswith("manual:")


def test_manual_provider_update() -> None:
    clock = Clock()
    manual = ManualProvider(lat=43.0, lon=-79.0, label="A", time_fn=clock)
    manual.update(lat=44.0, lon=-80.0, label="B")
    loc = manual.current()
    assert loc is not None and loc.lat == 44.0 and loc.source == "manual:B"


# ---------------------------------------------------------------------------
# Manager construction validation
# ---------------------------------------------------------------------------


def test_invalid_thresholds_raise() -> None:
    with pytest.raises(ValueError):
        LocationManager(phone=PhoneProvider(), stale_warning_seconds=0)
    with pytest.raises(ValueError):
        LocationManager(
            phone=PhoneProvider(),
            stale_warning_seconds=1000,
            expired_seconds=500,
        )


def test_invalid_primary_source_raises() -> None:
    mgr = LocationManager(phone=PhoneProvider())
    with pytest.raises(ValueError):
        mgr.set_primary_source("bogus")  # type: ignore[arg-type]
