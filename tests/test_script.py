"""Tests for the QSO conversation scripts."""

from __future__ import annotations

import random

from conversational_morse.config import StationConfig
from conversational_morse.qso.models import (
    DxStation,
    Expectation,
    QsoLength,
    QsoMode,
    Speaker,
)
from conversational_morse.qso.script import (
    build_conversation,
    grade,
    greeting_for_hour,
    normalize,
)

STATION = StationConfig(
    callsign="W6ABC",
    name="JIM",
    qth="FRESNO, CA",
    rig="IC-7300",
    antenna="DIPOLE",
    age=55,
    years_licensed=25,
    key_type="PADDLE",
    weather="RAIN",
    temperature_f=50,
)
DX = DxStation(callsign="DL1ABC", name="HANS", qth="MUNICH, DE")


def test_normalize_strips_punctuation_and_case() -> None:
    assert normalize("QTH Fresno, CA!") == "QTHFRESNOCA"


def test_greeting_for_hour() -> None:
    assert greeting_for_hour(8) == "GM"
    assert greeting_for_hour(14) == "GA"
    assert greeting_for_hour(21) == "GE"


def test_user_calls_cq_starts_with_qrl_and_cq() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.USER_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(1),
    )
    assert turns[0].speaker is Speaker.USER
    assert "QRL?" in turns[0].text
    assert turns[1].text == "CQ CQ DE W6ABC W6ABC K"
    assert turns[2].speaker is Speaker.DX
    assert turns[2].text == "W6ABC DE DL1ABC DL1ABC K"


def test_dx_calls_cq_starts_with_dx() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(1),
    )
    assert turns[0].speaker is Speaker.DX
    assert turns[0].text == "CQ CQ DE DL1ABC DL1ABC K"
    assert turns[1].speaker is Speaker.USER


def test_short_length_excludes_protocol_two_and_three() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(2),
    )
    labels = {turn.label for turn in turns}
    assert "P2" not in labels
    assert "P3" not in labels


def test_full_length_includes_all_protocols() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.FULL,
        rng=random.Random(2),
    )
    labels = {turn.label for turn in turns}
    assert {"P1", "P2", "P3", "END", "73"} <= labels


def test_conversation_ends_with_two_dits() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(3),
    )
    assert turns[-1].is_two_dits
    assert turns[-1].text == "E E"


def test_protocol_one_contains_user_details() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.USER_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(4),
    )
    user_p1 = next(
        turn for turn in turns if turn.label == "P1" and turn.speaker is Speaker.USER
    )
    assert "UR RST 599 599" in user_p1.text
    assert "QTH FRESNO, CA FRESNO, CA" in user_p1.text
    assert "NAME JIM JIM" in user_p1.text


def test_grade_reports_found_and_missing() -> None:
    expectations = (
        Expectation("CALL", ("W6ABC",)),
        Expectation("RST", ("599", "5NN")),
        Expectation("NAME", ("JIM",)),
    )
    report = grade("W6ABC UR RST 5NN", expectations)
    assert report.found == ("CALL", "RST")
    assert report.missing == ("NAME",)
    assert report.percent == 67
    assert report.is_solid is False


def test_grade_full_marks_solid() -> None:
    expectations = (Expectation("CALL", ("W6ABC",)),)
    report = grade("W6ABC DE W6ABC", expectations)
    assert report.percent == 100
    assert report.is_solid is True


def test_grade_without_expectations_is_full_marks() -> None:
    report = grade("anything", ())
    assert report.total == 0
    assert report.percent == 100
