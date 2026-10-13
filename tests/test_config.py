"""Tests for configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from conversational_morse.config import AppConfig, KeyerConfig, StationConfig


def test_callsign_is_upper_cased_and_trimmed() -> None:
    station = StationConfig(callsign="  w6abc ")
    assert station.callsign == "W6ABC"


def test_blank_callsign_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StationConfig(callsign="   ")


def test_text_fields_are_upper_cased() -> None:
    station = StationConfig(callsign="N0CALL", name="jim", qth="fresno, ca")
    assert station.name == "JIM"
    assert station.qth == "FRESNO, CA"


@pytest.mark.parametrize("wpm", [4, 100])
def test_keyer_wpm_bounds(wpm: int) -> None:
    with pytest.raises(ValidationError):
        KeyerConfig(wpm=wpm)


def test_keyer_defaults() -> None:
    keyer = KeyerConfig()
    assert keyer.baudrate == 1200
    assert keyer.paddle_echo is True


def test_default_app_config_has_station_and_keyer() -> None:
    config = AppConfig.default()
    assert config.station.callsign == "N0CALL"
    assert config.keyer.wpm == 20
