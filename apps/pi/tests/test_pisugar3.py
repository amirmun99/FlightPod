"""Tests for the PiSugar 3 client + battery provider."""

from __future__ import annotations

import socket
import threading
from contextlib import closing

import pytest

from flightpaper.hardware.battery import (
    NullBatteryProvider,
    PiSugar3BatteryProvider,
    make_battery_provider,
)
from flightpaper.hardware.pisugar3 import PiSugar3Client


class FakeServer:
    """Minimal line-server that drains commands and replies from a map."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.received: list[str] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            with closing(conn):
                conn.settimeout(0.5)
                try:
                    data = conn.recv(256).decode("ascii", errors="replace").strip()
                except OSError:
                    continue
                self.received.append(data)
                reply = self.responses.get(data)
                if reply is not None:
                    try:
                        conn.sendall((reply + "\n").encode("ascii"))
                    except OSError:
                        pass

    def stop(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=1.0)


@pytest.fixture
def fake_pisugar_server() -> FakeServer:
    server = FakeServer(
        {
            "get battery": "battery: 82.5",
            "get battery_charging": "battery_charging: false",
            "get battery_power_plugged": "battery_power_plugged: true",
        }
    )
    yield server
    server.stop()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def test_battery_percent_parses_response(fake_pisugar_server: FakeServer) -> None:
    client = PiSugar3Client(host="127.0.0.1", port=fake_pisugar_server.port, timeout=0.5)
    assert client.battery_percent() == pytest.approx(82.5)


def test_charging_parses_bool(fake_pisugar_server: FakeServer) -> None:
    client = PiSugar3Client(host="127.0.0.1", port=fake_pisugar_server.port, timeout=0.5)
    assert client.charging() is False


def test_external_power_parses_bool(fake_pisugar_server: FakeServer) -> None:
    client = PiSugar3Client(host="127.0.0.1", port=fake_pisugar_server.port, timeout=0.5)
    assert client.external_power() is True


def test_unreachable_server_returns_none() -> None:
    # Closed port: choose a random high port unlikely to be open.
    client = PiSugar3Client(host="127.0.0.1", port=1, timeout=0.2)
    assert client.battery_percent() is None
    assert client.charging() is None
    assert client.external_power() is None


def test_malformed_response_returns_none() -> None:
    server = FakeServer({"get battery": "not-a-valid-line"})
    try:
        client = PiSugar3Client(host="127.0.0.1", port=server.port, timeout=0.5)
        assert client.battery_percent() is None
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


def test_provider_round_trip(fake_pisugar_server: FakeServer) -> None:
    client = PiSugar3Client(host="127.0.0.1", port=fake_pisugar_server.port, timeout=0.5)
    provider = PiSugar3BatteryProvider(client)
    status = provider.read()
    # int(round(82.5)) is banker-rounded under Python 3 (→ 82).
    assert status.percent in (82, 83)
    assert status.charging is False
    assert status.external_power is True
    assert status.available is True


def test_null_provider_always_unavailable() -> None:
    provider = NullBatteryProvider()
    assert provider.read().available is False


def test_factory_unknown_provider_falls_back_to_null() -> None:
    provider = make_battery_provider(provider_name="not-a-thing")
    assert isinstance(provider, NullBatteryProvider)


def test_factory_pisugar_returns_pisugar_provider() -> None:
    provider = make_battery_provider(provider_name="pisugar3", pisugar_port=9999)
    assert isinstance(provider, PiSugar3BatteryProvider)
