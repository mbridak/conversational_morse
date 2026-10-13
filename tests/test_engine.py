"""Tests for the QSO engine state machine."""

from __future__ import annotations

import random

import pytest

from conversational_morse.config import StationConfig
from conversational_morse.qso import QsoEngine, QsoLength, QsoMode, Speaker
from conversational_morse.qso.models import DxStation

STATION = StationConfig(callsign="W6ABC", name="JIM", qth="FRESNO, CA")
DX = DxStation(callsign="DL1ABC", name="HANS", qth="MUNICH, DE")


def _engine() -> QsoEngine:
    return QsoEngine.create(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(7),
    )


def test_engine_starts_at_first_turn() -> None:
    engine = _engine()
    assert engine.index == 0
    assert engine.is_finished is False
    assert engine.current_turn is not None


def test_engine_advances_and_finishes() -> None:
    engine = _engine()
    total = len(engine.turns)
    for _ in range(total):
        engine.advance()
    assert engine.is_finished is True
    assert engine.current_turn is None


def test_advance_past_end_is_safe() -> None:
    engine = _engine()
    for _ in range(len(engine.turns) + 5):
        engine.advance()
    assert engine.is_finished is True


def test_engine_requires_turns() -> None:
    with pytest.raises(ValueError):
        QsoEngine([], "W6ABC")


def test_model_answer_matches_current_user_turn() -> None:
    engine = QsoEngine.create(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(7),
    )
    engine.advance()  # move to the user's answer turn
    assert engine.is_user_turn is True
    assert engine.model_answer() == "DL1ABC DE W6ABC W6ABC K"


def test_grade_current_uses_turn_expectations() -> None:
    engine = QsoEngine.create(
        STATION,
        DX,
        QsoMode.DX_CALLS_CQ,
        QsoLength.SHORT,
        rng=random.Random(7),
    )
    engine.advance()
    report = engine.grade_current("DL1ABC DE W6ABC W6ABC K")
    assert report.percent == 100


def test_progress_reports_index_and_total() -> None:
    engine = _engine()
    index, total = engine.progress()
    assert index == 0
    assert total == len(engine.turns)


def test_record_appends_to_transcript() -> None:
    engine = _engine()
    engine.record(Speaker.USER, "TEST")
    assert engine.transcript == [(Speaker.USER, "TEST")]


def test_model_answer_on_finished_engine_raises() -> None:
    engine = _engine()
    for _ in range(len(engine.turns)):
        engine.advance()
    with pytest.raises(ValueError):
        engine.model_answer()
