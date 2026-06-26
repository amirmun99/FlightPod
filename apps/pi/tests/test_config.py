"""Tests for flightpaper.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from flightpaper.config import AppConfig, dump_config, load_config


def test_defaults_match_spec() -> None:
    cfg = AppConfig()
    assert cfg.app.name == "FlightPaper"
    assert cfg.api.port == 8080
    assert cfg.opensky.update_interval_seconds == 20
    assert cfg.opensky.battery_saver_interval_seconds == 60
    assert cfg.display.driver == "waveshare_2in13_rev2_1"
    assert cfg.display.width == 250
    assert cfg.display.height == 122
    assert cfg.ui.radius_km == 25
    assert cfg.ui.distance_units == "km"
    assert cfg.battery.provider == "pisugar3"
    assert cfg.battery.pisugar_port == 8423


def test_example_yaml_loads(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[1] / "config.example.yml"
    cfg = load_config(example)
    # Round-trip should give back the same defaults.
    default = AppConfig()
    assert cfg.app.name == default.app.name
    assert cfg.display.driver == default.display.driver


def test_partial_override(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text("ui:\n  radius_km: 50\nopensky:\n  update_interval_seconds: 30\n")
    cfg = load_config(cfg_path)
    assert cfg.ui.radius_km == 50
    assert cfg.opensky.update_interval_seconds == 30
    # Untouched section keeps defaults.
    assert cfg.display.default_page == "radar"


def test_invalid_lat_rejected(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text(
        "location:\n  manual:\n    enabled: true\n    lat: 100.0\n    lon: 0.0\n"
    )
    with pytest.raises(Exception):  # pydantic.ValidationError
        load_config(cfg_path)


def test_invalid_port_rejected(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text("api:\n  port: 70000\n")
    with pytest.raises(Exception):
        load_config(cfg_path)


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.yml"
    cfg = load_config(missing)
    # Falls back to defaults rather than raising.
    assert cfg.app.name == "FlightPaper"


def test_env_var_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text("ui:\n  radius_km: 10\n")
    monkeypatch.setenv("FLIGHTPAPER_CONFIG", str(cfg_path))
    cfg = load_config()
    assert cfg.ui.radius_km == 10


def test_dump_config_round_trips() -> None:
    cfg = AppConfig()
    cfg.ui.radius_km = 100.0
    text = dump_config(cfg)
    assert "radius_km: 100" in text
