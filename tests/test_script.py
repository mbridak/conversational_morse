"""Tests for the QSO conversation scripts."""

from __future__ import annotations

import random

from conversational_morse.config import StationConfig
from conversational_morse.qso.models import (
    CopyReport,
    DxStation,
    Expectation,
    QsoLength,
    QsoMode,
    Speaker,
)
from conversational_morse.qso.script import (
    build_conversation,
    find_wrong_callsigns,
    grade,
    greeting_for_hour,
    normalize,
    repeat_request,
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


def test_every_user_turn_is_checkable() -> None:
    """Each portion the operator sends must carry something to be graded."""
    for mode in (QsoMode.USER_CALLS_CQ, QsoMode.DX_CALLS_CQ):
        for length in (QsoLength.SHORT, QsoLength.MEDIUM, QsoLength.FULL):
            turns = build_conversation(
                STATION,
                DX,
                mode,
                length,
                rng=random.Random(0),
            )
            for turn in turns:
                if turn.speaker is Speaker.USER:
                    assert turn.expectations, (mode, length, turn.label)


def test_grade_without_expectations_is_full_marks() -> None:
    report = grade("anything", ())
    assert report.total == 0
    assert report.percent == 100


def test_callsign_expectation_requires_every_call() -> None:
    expectations = (Expectation("CALL", ("W6ABC", "DL1ABC"), require_all=True),)
    assert grade("DL1ABC DE W6ABC", expectations).missing == ()
    only_mine = grade("W6ABC K", expectations)
    assert only_mine.missing == ("CALL",)
    assert only_mine.is_complete is False


def test_grade_flags_wrong_callsign() -> None:
    expectations = (Expectation("CALL", ("W6ABC", "DL1ABC"), require_all=True),)
    report = grade("DL1ABC DE W7XYZ", expectations)
    assert report.wrong == ("W7XYZ",)
    assert report.missing == ("CALL",)
    assert report.is_complete is False


def test_grade_ignores_rig_like_tokens_as_callsigns() -> None:
    expectations = (Expectation("CALL", ("W6ABC", "DL1ABC"), require_all=True),)
    report = grade("DL1ABC DE W6ABC RIG FTDX101 PWR 100W", expectations)
    assert report.wrong == ()
    assert report.is_complete is True


def test_answering_cq_needs_the_dx_call() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(1),
    )
    answer = next(
        turn
        for turn in turns
        if turn.label == "ANSWER" and turn.speaker is Speaker.USER
    )
    complete = grade(f"{DX.callsign} DE {STATION.callsign}", answer.expectations)
    assert complete.is_complete is True
    incomplete = grade(f"{STATION.callsign} K", answer.expectations)
    assert incomplete.is_complete is False
    assert incomplete.missing == ("CALL",)


def test_find_wrong_callsigns_returns_unique_mismatches() -> None:
    assert find_wrong_callsigns("K6GTE K7XYZ K7XYZ", frozenset({"K6GTE"})) == ("K7XYZ",)


def test_repeat_request_names_missing_items() -> None:
    report = CopyReport(found=("CALL",), missing=("QTH", "NAME"))
    assert repeat_request("DL1ABC", "W6ABC", report) == (
        "W6ABC DE DL1ABC QTH? NAME? AGN W6ABC DE DL1ABC K"
    )


def test_repeat_request_flags_wrong_call() -> None:
    report = CopyReport(found=(), missing=("CALL",), wrong=("W7XYZ",))
    request = repeat_request("DL1ABC", "W6ABC", report)
    assert request.count("CALL?") == 1
