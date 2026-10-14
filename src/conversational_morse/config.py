"""Pydantic configuration models for the application and the keyer."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field, field_validator

DEFAULT_CALLSIGN = "N0CALL"

SIDETONE_VOLUME_LEVELS: Final[tuple[str, ...]] = ("normal", "low")


class StationConfig(BaseModel):
    """The operator's own station details used to build QSO exchanges."""

    callsign: str = DEFAULT_CALLSIGN
    name: str = "OPERATOR"
    qth: str = "ANYTOWN, USA"
    rig: str = "IC-7300"
    power: str = "100W"
    antenna: str = "DIPOLE UP 45 FT"
    age: int = Field(default=45, ge=0, le=120)
    years_licensed: int = Field(default=10, ge=0, le=100)
    key_type: str = "BENCHER PADDLE"
    weather: str = "CLR"
    temperature_f: int = Field(default=70, ge=-80, le=140)

    @field_validator("callsign")
    @classmethod
    def _normalise_callsign(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            msg = "callsign must not be empty"
            raise ValueError(msg)
        return cleaned

    @field_validator("name", "qth", "rig", "antenna", "key_type", "weather")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    def greeting(self) -> str:
        """Return a time-of-day greeting proword used to open a QSO."""
        return "GE"


class KeyerConfig(BaseModel):
    """Session behaviour and the settings applied to the keyer device."""

    port: str | None = None
    baudrate: int = Field(default=1200, ge=1200, le=9600)
    wpm: int = Field(default=20, ge=5, le=99)
    sidetone_index: int = Field(default=5, ge=0, le=10)
    sidetone_volume: str = "normal"
    paddle_echo: bool = True
    autospace: bool = True
    lead_in_ms: int = Field(default=10, ge=0, le=250)
    tail_ms: int = Field(default=10, ge=0, le=250)
    over_idle_seconds: float = Field(default=2.5, gt=0.5, le=10.0)
    require_correct_copy: bool = True
    show_dx_output: bool = True
    use_simulator: bool = False

    @field_validator("sidetone_volume")
    @classmethod
    def _valid_sidetone_volume(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in SIDETONE_VOLUME_LEVELS:
            msg = "sidetone_volume must be 'normal' or 'low'"
            raise ValueError(msg)
        return cleaned


class AppConfig(BaseModel):
    """Top level application configuration."""

    station: StationConfig = Field(default_factory=StationConfig)
    keyer: KeyerConfig = Field(default_factory=KeyerConfig)

    @classmethod
    def default(cls) -> AppConfig:
        return cls()
