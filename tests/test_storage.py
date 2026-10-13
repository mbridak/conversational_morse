"""Tests for configuration persistence."""

from __future__ import annotations

from pathlib import Path

from conversational_morse.config import AppConfig, StationConfig
from conversational_morse.storage import load_config, save_config


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "does-not-exist.json")
    assert config.station.callsign == "N0CALL"


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.json"
    original = AppConfig.default()
    original.station = StationConfig(callsign="W6ABC", name="JIM", qth="FRESNO, CA")
    original.keyer.wpm = 28

    save_config(original, path)
    assert path.exists()

    loaded = load_config(path)
    assert loaded.station.callsign == "W6ABC"
    assert loaded.keyer.wpm == 28


def test_corrupt_file_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    config = load_config(path)
    assert config.station.callsign == "N0CALL"
