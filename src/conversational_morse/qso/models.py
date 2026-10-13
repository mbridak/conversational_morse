"""Data models for simulating a Morse code contact."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field


class StationLike(Protocol):
    """Anything carrying enough station detail to build a QSO exchange."""

    callsign: str
    name: str
    qth: str
    rig: str
    power: str
    antenna: str
    age: int
    years_licensed: int
    key_type: str
    weather: str
    temperature_f: int


class Speaker(StrEnum):
    """Who is sending a given turn."""

    USER = "user"
    DX = "dx"


class QsoMode(StrEnum):
    """Who initiates the contact."""

    USER_CALLS_CQ = "user_calls_cq"
    DX_CALLS_CQ = "dx_calls_cq"


class QsoLength(StrEnum):
    """How much of the exchange protocol to run."""

    SHORT = "short"
    MEDIUM = "medium"
    FULL = "full"


class DxStation(BaseModel):
    """The simulated station the operator works."""

    callsign: str
    name: str
    qth: str
    rig: str = "IC-7300"
    power: str = "100W"
    antenna: str = "DIPOLE"
    age: int = Field(default=45, ge=0, le=120)
    years_licensed: int = Field(default=15, ge=0, le=100)
    key_type: str = "PADDLE"
    weather: str = "CLR"
    temperature_f: int = Field(default=70, ge=-80, le=140)
    rst: str = "599"


_DX_POOL: tuple[dict[str, object], ...] = (
    {
        "callsign": "DL1ABC",
        "name": "HANS",
        "qth": "MUNICH, DE",
        "rig": "FTDX101",
        "power": "100W",
        "antenna": "VERTICAL",
        "age": 58,
        "years_licensed": 30,
        "key_type": "BENCHER",
        "weather": "RAIN",
        "temperature_f": 52,
    },
    {
        "callsign": "JA1XYZ",
        "name": "KENJI",
        "qth": "TOKYO, JP",
        "rig": "IC-7610",
        "power": "200W",
        "antenna": "YAGI 3EL",
        "age": 47,
        "years_licensed": 22,
        "key_type": "IAMBIC",
        "weather": "CLR",
        "temperature_f": 68,
    },
    {
        "callsign": "G4DEF",
        "name": "PETER",
        "qth": "BRISTOL, UK",
        "rig": "K3",
        "power": "100W",
        "antenna": "DOUBLE T",
        "age": 63,
        "years_licensed": 41,
        "key_type": "BUG",
        "weather": "DRIZZLE",
        "temperature_f": 55,
    },
    {
        "callsign": "VK2HIJ",
        "name": "MARG",
        "qth": "SYDNEY, AU",
        "rig": "FT-991A",
        "power": "50W",
        "antenna": "DIPOLE",
        "age": 39,
        "years_licensed": 12,
        "key_type": "PADDLE",
        "weather": "SMOKE",
        "temperature_f": 79,
    },
    {
        "callsign": "K5KLM",
        "name": "BILL",
        "qth": "DALLAS, TX",
        "rig": "TS-590",
        "power": "100W",
        "antenna": "TRIBANDER",
        "age": 71,
        "years_licensed": 48,
        "key_type": "STRAIGHT KEY",
        "weather": "CLR",
        "temperature_f": 88,
    },
    {
        "callsign": "VE3NOP",
        "name": "ANNE",
        "qth": "TORONTO, CA",
        "rig": "IC-7300",
        "power": "100W",
        "antenna": "END FED",
        "age": 52,
        "years_licensed": 18,
        "key_type": "BENCHER",
        "weather": "SNOW",
        "temperature_f": 24,
    },
    {
        "callsign": "EA4QRS",
        "name": "CARLOS",
        "qth": "MADRID, ES",
        "rig": "FT-450",
        "power": "80W",
        "antenna": "VERTICAL",
        "age": 44,
        "years_licensed": 20,
        "key_type": "PADDLE",
        "weather": "CLR",
        "temperature_f": 61,
    },
    {
        "callsign": "PY2TUV",
        "name": "PAULO",
        "qth": "SAO PAULO, BR",
        "rig": "IC-7100",
        "power": "100W",
        "antenna": "WINDOM",
        "age": 36,
        "years_licensed": 9,
        "key_type": "IAMBIC",
        "weather": "RAIN",
        "temperature_f": 82,
    },
)


def random_dx_station(rng: random.Random | None = None) -> DxStation:
    """Return a randomly chosen plausible DX station."""
    chooser = rng if rng is not None else random.Random()
    return DxStation.model_validate(chooser.choice(_DX_POOL))


@dataclass(frozen=True)
class Expectation:
    """A single piece of information the operator is expected to send."""

    label: str
    patterns: tuple[str, ...]
    require_all: bool = False


@dataclass(frozen=True)
class Turn:
    """One station's transmission within the conversation."""

    speaker: Speaker
    label: str
    text: str
    hint: str = ""
    expectations: tuple[Expectation, ...] = ()
    is_two_dits: bool = field(default=False)


@dataclass(frozen=True)
class CopyReport:
    """How much of the expected information the operator actually sent."""

    found: tuple[str, ...]
    missing: tuple[str, ...]
    wrong: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.found) + len(self.missing)

    @property
    def is_complete(self) -> bool:
        """True when nothing expected was missing and no wrong call was sent."""
        return not self.missing and not self.wrong

    @property
    def percent(self) -> int:
        if self.total == 0:
            return 100
        return round(100 * len(self.found) / self.total)

    @property
    def is_solid(self) -> bool:
        return self.percent >= 80
