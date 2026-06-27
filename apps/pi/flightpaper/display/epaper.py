"""ePaper driver interface + driver registry.

Every concrete driver implements :class:`EPaperDriver`. The
:func:`make_driver` factory consults the registry and falls back to
:class:`NullEPaperDriver` whenever:

* the requested driver name isn't registered,
* the driver's hardware backend (e.g. ``waveshare_epd`` package, SPI) is
  unavailable on this machine.

This keeps the rest of the codebase identical between Pi and macOS dev.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

log = logging.getLogger(__name__)


@runtime_checkable
class EPaperDriver(Protocol):
    width: int
    height: int

    def init(self) -> None: ...
    def display_full(self, image: "PILImage") -> None: ...
    def display_partial(self, image: "PILImage") -> None: ...
    def clear(self) -> None: ...
    def sleep(self) -> None: ...
    def cleanup(self) -> None: ...


# ---------------------------------------------------------------------------
# Null driver — always works, for macOS dev + unit tests.
# ---------------------------------------------------------------------------


class NullEPaperDriver:
    """Stores the most recently 'displayed' image for inspection.

    Used on dev hosts and any time the configured hardware driver isn't
    importable. Tests can read ``last_image`` to verify the renderer ran.
    """

    name = "null"

    def __init__(self, *, width: int, height: int, rotation: int = 0) -> None:
        self.width = width
        self.height = height
        self.rotation = rotation
        self.last_image: "PILImage" | None = None
        self.full_calls: int = 0
        self.partial_calls: int = 0
        self.cleared: bool = False
        self.is_asleep: bool = False
        self.is_initialized: bool = False

    def init(self) -> None:
        self.is_initialized = True
        log.debug("null ePaper driver initialised (%dx%d)", self.width, self.height)

    def display_full(self, image: "PILImage") -> None:
        self.last_image = image
        self.full_calls += 1

    def display_partial(self, image: "PILImage") -> None:
        self.last_image = image
        self.partial_calls += 1

    def clear(self) -> None:
        self.last_image = None
        self.cleared = True

    def sleep(self) -> None:
        self.is_asleep = True

    def cleanup(self) -> None:
        self.is_asleep = True
        self.is_initialized = False


# ---------------------------------------------------------------------------
# Driver registry
# ---------------------------------------------------------------------------


DriverFactory = Callable[[int, int, int], EPaperDriver]

_REGISTRY: dict[str, DriverFactory] = {
    "null": lambda w, h, r: NullEPaperDriver(width=w, height=h, rotation=r),
}


def register_driver(name: str, factory: DriverFactory) -> None:
    _REGISTRY[name] = factory


def list_drivers() -> list[str]:
    return sorted(_REGISTRY.keys())


def make_driver(name: str, *, width: int, height: int, rotation: int = 0) -> EPaperDriver:
    """Build a driver by name, falling back to ``null`` if anything goes wrong."""

    factory = _REGISTRY.get(name)
    if factory is None:
        log.warning("unknown display driver %r; using null", name)
        return NullEPaperDriver(width=width, height=height, rotation=rotation)
    try:
        return factory(width, height, rotation)
    except (ImportError, OSError, RuntimeError) as exc:
        log.warning(
            "display driver %r unavailable (%s); falling back to null",
            name,
            exc,
        )
        return NullEPaperDriver(width=width, height=height, rotation=rotation)


# Eagerly register the Waveshare shims so ``make_driver("waveshare_2in13_v4")``
# (and the V2/Rev2.1 variant) work on the Pi. The actual hardware import is
# deferred to driver construction / ``init``.
from . import waveshare_driver  # noqa: E402, F401 - side-effect import (V2/Rev2.1)
from . import waveshare_driver_v4  # noqa: E402, F401 - side-effect import (V4)


__all__ = [
    "EPaperDriver",
    "NullEPaperDriver",
    "list_drivers",
    "make_driver",
    "register_driver",
]
