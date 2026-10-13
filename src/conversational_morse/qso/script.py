"""Build realistic CW QSO conversations from the W6JIM protocol sheet.

The conversation is expressed as a flat list of :class:`Turn` objects. Each
turn is either a transmission from the simulated DX station or one the operator
is expected to key. User turns carry the model answer plus the information the
operator should include, which the engine later grades.
"""

from __future__ import annotations

import random

from ..config import StationConfig
from .models import (
    CopyReport,
    DxStation,
    Expectation,
    QsoLength,
    QsoMode,
    Speaker,
    StationLike,
    Turn,
)

RST_PATTERNS: tuple[str, ...] = ("599", "5NN")


def greeting_for_hour(hour: int) -> str:
    """Return the conventional Morse greeting for a time of day."""
    if hour < 12:
        return "GM"
    if hour < 18:
        return "GA"
    return "GE"


def normalize(text: str) -> str:
    """Uppercase and strip everything except letters and digits."""
    return "".join(char for char in text.upper() if char.isalnum())


def _callsign_exchange(sender: StationLike, other: StationLike) -> tuple[str, str]:
    header = f"{other.callsign} DE {sender.callsign}"
    footer = f"{other.callsign} DE {sender.callsign} K"
    return header, footer


def _callsign_expectations(
    *stations: StationLike,
    label: str = "CALL",
) -> Expectation:
    return Expectation(label, tuple(s.callsign for s in stations))


def protocol_one(
    sender: StationLike,
    other: StationLike,
    *,
    greeting: str,
    opener: str,
) -> str:
    """Build a protocol-1 over (RST, QTH and name)."""
    header, footer = _callsign_exchange(sender, other)
    return " ".join(
        [
            header,
            f"{greeting} ES TNX FER {opener}",
            f"UR RST {RST_PATTERNS[0]} {RST_PATTERNS[0]}",
            f"QTH {sender.qth} {sender.qth}",
            f"NAME {sender.name} {sender.name}",
            "OK HW? AR",
            footer,
        ],
    )


def protocol_two(sender: StationLike, other: StationLike) -> str:
    """Build a protocol-2 over (rig, power, antenna and weather)."""
    header, footer = _callsign_exchange(sender, other)
    return " ".join(
        [
            header,
            f"OK {other.name} FB ES TNX FER RPRT",
            f"RIG {sender.rig} ES PWR {sender.power}",
            f"ANT {sender.antenna}",
            f"WX {sender.weather} ES TEMP {sender.temperature_f}F",
            f"OK {other.name} HW? AR",
            footer,
        ],
    )


def protocol_three(sender: StationLike, other: StationLike) -> str:
    """Build a protocol-3 over (age, years licensed and key)."""
    header, footer = _callsign_exchange(sender, other)
    return " ".join(
        [
            header,
            f"OK {other.name} SOLID CPY",
            f"AGE {sender.age} YRS",
            f"BEEN HAM FER {sender.years_licensed} YRS",
            f"MY KEY {sender.key_type}",
            f"OK {other.name} HW? AR",
            footer,
        ],
    )


def ending_starter(sender: StationLike, other: StationLike) -> str:
    """Build the transmission that initiates the sign-off."""
    header, footer = _callsign_exchange(sender, other)
    return " ".join(
        [
            header,
            f"OK {other.name} TNX FER FB QSO",
            "ES HP CUAGN 73 AR",
            footer.replace(" K", " TU SK"),
        ],
    )


def ending_responder(sender: StationLike, other: StationLike) -> str:
    """Build the reply to a sign-off, which also carries a final SK."""
    header, footer = _callsign_exchange(sender, other)
    return " ".join(
        [
            header,
            "OK TNX FER FB QSO ES BEST 73",
            footer.replace(" K", " TU SK"),
        ],
    )


def _user_protocol_one(
    user: StationConfig,
    dx: DxStation,
    greeting: str,
    opener: str,
) -> Turn:
    text = protocol_one(user, dx, greeting=greeting, opener=opener)
    expectations = (
        _callsign_expectations(user, dx),
        Expectation("RST", RST_PATTERNS),
        Expectation("QTH", (normalize(user.qth),)),
        Expectation("NAME", (normalize(user.name),)),
    )
    hint = f"Send your RST, QTH ({user.qth}) and name ({user.name})."
    return Turn(Speaker.USER, "P1", text, hint, expectations)


def _user_protocol_two(user: StationConfig, dx: DxStation) -> Turn:
    text = protocol_two(user, dx)
    expectations = (
        _callsign_expectations(user, dx),
        Expectation("RIG", (normalize(user.rig),)),
        Expectation("ANT", (normalize(user.antenna),)),
        Expectation("WX", (normalize(user.weather),)),
    )
    hint = "Share your rig, power, antenna and the weather."
    return Turn(Speaker.USER, "P2", text, hint, expectations)


def _user_protocol_three(user: StationConfig, dx: DxStation) -> Turn:
    text = protocol_three(user, dx)
    expectations = (
        _callsign_expectations(user, dx),
        Expectation("AGE", (str(user.age),)),
        Expectation("YRS", (str(user.years_licensed),)),
        Expectation("KEY", (normalize(user.key_type),)),
    )
    hint = "Share your age, years as a ham and the key you are using."
    return Turn(Speaker.USER, "P3", text, hint, expectations)


def _two_dits(speaker: Speaker) -> Turn:
    return Turn(
        speaker,
        "73",
        "E E",
        hint="Send the two closing dits (dit dit).",
        is_two_dits=True,
    )


def build_conversation(
    user: StationConfig,
    dx: DxStation,
    mode: QsoMode,
    length: QsoLength = QsoLength.FULL,
    rng: random.Random | None = None,
    hour: int = 12,
) -> list[Turn]:
    """Assemble the full list of turns for the requested contact."""
    chooser = rng if rng is not None else random.Random()
    greeting = greeting_for_hour(hour)
    turns: list[Turn] = []

    if mode is QsoMode.USER_CALLS_CQ:
        turns.append(
            Turn(
                Speaker.USER,
                "QRL",
                "QRL? QRL?",
                hint="First check the frequency is clear by sending QRL? twice.",
            ),
        )
        turns.append(
            Turn(
                Speaker.USER,
                "CQ",
                f"CQ CQ DE {user.callsign} {user.callsign} K",
                hint="Call CQ in a 2 by 2 format.",
                expectations=(_callsign_expectations(user),),
            ),
        )
        turns.append(
            Turn(
                Speaker.DX,
                "ANSWER",
                f"{user.callsign} DE {dx.callsign} {dx.callsign} K",
            ),
        )
        turns.append(_user_protocol_one(user, dx, greeting, "CALL"))
        turns.append(
            Turn(
                Speaker.DX,
                "P1",
                protocol_one(dx, user, greeting=greeting, opener="RPRT"),
            ),
        )
    else:
        turns.append(
            Turn(
                Speaker.DX,
                "CQ",
                f"CQ CQ DE {dx.callsign} {dx.callsign} K",
            ),
        )
        turns.append(
            Turn(
                Speaker.USER,
                "ANSWER",
                f"{dx.callsign} DE {user.callsign} {user.callsign} K",
                hint="Answer the CQ with their call DE your call, twice.",
                expectations=(_callsign_expectations(user, dx),),
            ),
        )
        turns.append(
            Turn(
                Speaker.DX,
                "P1",
                protocol_one(dx, user, greeting=greeting, opener="CALL"),
            ),
        )
        turns.append(_user_protocol_one(user, dx, greeting, "RPRT"))

    if length in (QsoLength.MEDIUM, QsoLength.FULL):
        turns.append(Turn(Speaker.DX, "P2", protocol_two(dx, user)))
        turns.append(_user_protocol_two(user, dx))

    if length is QsoLength.FULL:
        turns.append(Turn(Speaker.DX, "P3", protocol_three(dx, user)))
        turns.append(_user_protocol_three(user, dx))

    # The station that did not answer the CQ traditionally starts the ending.
    user_starts_ending = mode is QsoMode.DX_CALLS_CQ
    if chooser.random() < 0.5:
        user_starts_ending = not user_starts_ending

    if user_starts_ending:
        turns.append(
            Turn(
                Speaker.USER,
                "END",
                ending_starter(user, dx),
                hint="Sign off with your thanks, 73 and SK.",
            ),
        )
        turns.append(Turn(Speaker.DX, "END", ending_responder(dx, user)))
        turns.append(_two_dits(Speaker.USER))
        turns.append(_two_dits(Speaker.DX))
    else:
        turns.append(Turn(Speaker.DX, "END", ending_starter(dx, user)))
        turns.append(
            Turn(
                Speaker.USER,
                "END",
                ending_responder(user, dx),
                hint="Answer their sign-off and send your own SK.",
            ),
        )
        turns.append(_two_dits(Speaker.DX))
        turns.append(_two_dits(Speaker.USER))

    return turns


def grade(text: str, expectations: tuple[Expectation, ...]) -> CopyReport:
    """Compare the operator's keyed text against the expected information."""
    haystack = normalize(text)
    found: list[str] = []
    missing: list[str] = []
    for expectation in expectations:
        if any(normalize(pattern) in haystack for pattern in expectation.patterns):
            found.append(expectation.label)
        else:
            missing.append(expectation.label)
    return CopyReport(tuple(found), tuple(missing))
