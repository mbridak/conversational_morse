"""The QSO state machine that walks through a generated conversation."""

from __future__ import annotations

import random

from ..config import StationConfig
from .models import (
    CopyReport,
    DxStation,
    QsoLength,
    QsoMode,
    Speaker,
    Turn,
)
from .script import build_conversation, grade


class QsoEngine:
    """Drives the operator through a simulated contact one turn at a time."""

    def __init__(
        self,
        turns: list[Turn],
        user_callsign: str,
        dx_callsign: str = "",
    ) -> None:
        if not turns:
            msg = "a conversation needs at least one turn"
            raise ValueError(msg)
        self._turns = turns
        self._index = 0
        self._user_callsign = user_callsign
        self._dx_callsign = dx_callsign
        self.transcript: list[tuple[Speaker, str]] = []

    @classmethod
    def create(
        cls,
        user: StationConfig,
        dx: DxStation,
        mode: QsoMode,
        length: QsoLength = QsoLength.FULL,
        rng: random.Random | None = None,
        hour: int = 12,
    ) -> QsoEngine:
        turns = build_conversation(user, dx, mode, length, rng, hour)
        return cls(turns, user.callsign, dx.callsign)

    @property
    def user_callsign(self) -> str:
        return self._user_callsign

    @property
    def dx_callsign(self) -> str:
        return self._dx_callsign

    @property
    def turns(self) -> list[Turn]:
        return list(self._turns)

    @property
    def index(self) -> int:
        return self._index

    @property
    def is_finished(self) -> bool:
        return self._index >= len(self._turns)

    @property
    def current_turn(self) -> Turn | None:
        if self.is_finished:
            return None
        return self._turns[self._index]

    @property
    def is_user_turn(self) -> bool:
        turn = self.current_turn
        return turn is not None and turn.speaker is Speaker.USER

    def model_answer(self) -> str:
        """The ideal text for the current user turn."""
        turn = self.current_turn
        if turn is None:
            msg = "the conversation is finished"
            raise ValueError(msg)
        return turn.text

    def grade_current(self, text: str) -> CopyReport:
        """Grade text against the current user turn without advancing."""
        turn = self.current_turn
        if turn is None:
            msg = "the conversation is finished"
            raise ValueError(msg)
        return grade(text, turn.expectations)

    def record(self, speaker: Speaker, text: str) -> None:
        self.transcript.append((speaker, text))

    def advance(self) -> Turn | None:
        """Move to the next turn and return it, or ``None`` when finished."""
        if not self.is_finished:
            self._index += 1
        return self.current_turn

    def progress(self) -> tuple[int, int]:
        return (self._index, len(self._turns))
