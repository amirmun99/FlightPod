"""Location provider protocol.

Concrete implementations live in :mod:`phone_provider` and
:mod:`manual_provider`. The :class:`LocationManager` composes them.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import Location


@runtime_checkable
class LocationProvider(Protocol):
    """Anything that can report a current :class:`Location` (or ``None``)."""

    source_name: str

    def current(self) -> Location | None: ...


__all__ = ["LocationProvider"]
