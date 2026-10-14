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
    parse_repeat_request,
    repeat_reply,
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
    assert turns[2].text == "DL1ABC DL1ABC"


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


def test_answering_cq_needs_only_your_own_call() -> None:
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
    known = (STATION.callsign, DX.callsign)

    # Sending just your own callsign is the correct way to answer a CQ.
    complete = grade(STATION.callsign, answer.expectations, known)
    assert complete.is_complete is True

    # Naming the DX while answering is not held against you either.
    with_dx_call = grade(
        f"{DX.callsign} {STATION.callsign}",
        answer.expectations,
        known,
    )
    assert with_dx_call.is_complete is True
    assert with_dx_call.wrong == ()

    # Sending only the DX call, without your own, fails the check.
    only_dx = grade(DX.callsign, answer.expectations, known)
    assert only_dx.is_complete is False
    assert only_dx.missing == ("CALL",)


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


def test_dx_turns_carry_repeat_phrases() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.FULL,
        rng=random.Random(5),
    )
    cq = turns[0]
    assert cq.speaker is Speaker.DX
    assert cq.repeat_phrases["CALL"] == "DL1ABC DL1ABC"

    by_label = {turn.label: turn for turn in turns if turn.speaker is Speaker.DX}
    assert by_label["P1"].repeat_phrases["QTH"] == "QTH MUNICH, DE MUNICH, DE"
    assert by_label["P2"].repeat_phrases["ANT"] == "ANT DIPOLE"
    assert by_label["P3"].repeat_phrases["YRS"] == "BEEN HAM FER 15 YRS"


def test_user_turns_have_no_repeat_phrases() -> None:
    turns = build_conversation(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.FULL,
        rng=random.Random(5),
    )
    user_turns = [turn for turn in turns if turn.speaker is Speaker.USER]
    assert all(not turn.repeat_phrases for turn in user_turns)


def test_parse_repeat_request_finds_known_items() -> None:
    items = parse_repeat_request(
        "QTH? NAME?",
        dx_callsign="DL1ABC",
        available=("CALL", "RST", "QTH", "NAME"),
    )
    assert items == ("QTH", "NAME")


def test_parse_repeat_request_partial_call_asks_for_call() -> None:
    assert parse_repeat_request(
        "W6?",
        dx_callsign="DL1ABC",
        available=("CALL", "RST"),
    ) == ("CALL",)
    assert parse_repeat_request(
        "DL1?",
        dx_callsign="DL1ABC",
        available=("CALL", "RST"),
    ) == ("CALL",)
    assert parse_repeat_request(
        "?",
        dx_callsign="DL1ABC",
        available=("CALL",),
    ) == ("CALL",)


def test_parse_repeat_request_ignores_ordinary_questions() -> None:
    assert (
        parse_repeat_request(
            "HW?",
            dx_callsign="DL1ABC",
            available=("CALL", "RST", "QTH"),
        )
        == ()
    )
    assert parse_repeat_request("", dx_callsign="DL1ABC", available=("CALL",)) == ()


def test_parse_repeat_request_deduplicates() -> None:
    items = parse_repeat_request(
        "QTH? QTH?",
        dx_callsign="DL1ABC",
        available=("QTH",),
    )
    assert items == ("QTH",)


def test_repeat_reply_for_call_is_sent_twice() -> None:
    assert repeat_reply("DL1ABC", "W6ABC", ("CALL",), {"CALL": "DL1ABC DL1ABC"}) == (
        "DL1ABC DL1ABC"
    )


def test_repeat_reply_wraps_other_items() -> None:
    reply = repeat_reply(
        "DL1ABC",
        "W6ABC",
        ("QTH",),
        {"QTH": "QTH MUNICH, DE MUNICH, DE"},
    )
    assert reply == "W6ABC DE DL1ABC QTH MUNICH, DE MUNICH, DE AGN W6ABC DE DL1ABC K"
