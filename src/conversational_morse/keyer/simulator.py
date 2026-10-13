"""A software WinKeyer emulation used for tests and hardware-free practice.

The simulator schedules the same events a real keyer would emit (status,
per-character echoes and completion) against an injectable clock, so tests can
step time deterministically while the GUI can simply use the wall clock.
"""

from __future__ import annotations

import heapq
import time
from collections.abc import Callable

from .. import morse
from .device import (
    EchoEvent,
    KeyerDevice,
    KeyerEvent,
    KeyerStatus,
    StatusEvent,
    TxCompleteEvent,
)

SIMULATED_REVISION = 0x17


class SimulatedKeyer(KeyerDevice):
    """A WinKeyer that exists only in software."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._open = False
        self._wpm = 20
        self._busy = False
        self._status = KeyerStatus.empty()
        self._timeline: list[tuple[float, int, KeyerEvent]] = []
        self._sequence = 0
        self._sent: list[str] = []
        self._buffer = ""

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def revision(self) -> int | None:
        return SIMULATED_REVISION if self._open else None

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def sent_text(self) -> list[str]:
        """Every text block passed to :meth:`send_text` in order."""
        return list(self._sent)

    def open(self) -> None:
        self._open = True
        self._busy = False
        self._status = KeyerStatus.empty()

    def close(self) -> None:
        self._open = False
        self._clear_timeline()

    def configure(
        self,
        *,
        wpm: int,
        sidetone_index: int,
        paddle_echo: bool,
        autospace: bool,
        lead_in_ms: int = 10,
        tail_ms: int = 10,
    ) -> None:
        self._wpm = wpm

    def set_wpm(self, wpm: int) -> None:
        self._wpm = wpm

    def send_text(self, text: str) -> None:
        if not self._open:
            msg = "simulated keyer is not open"
            raise RuntimeError(msg)
        self._sent.append(text)
        cursor = self._now()
        self._schedule(cursor, StatusEvent(self._status_with(busy=True)))
        for character in text:
            if character == " ":
                cursor += morse.dit_duration(self._wpm) * morse.WORD_SPACE_UNITS
                continue
            cursor += morse.character_duration(character, self._wpm)
            self._schedule(cursor, EchoEvent(character, from_paddle=False))
        self._schedule(cursor, StatusEvent(self._status_with(busy=False)))
        self._schedule(cursor, TxCompleteEvent())

    def simulate_paddle(self, text: str) -> None:
        """Feed text as if it were keyed on the paddles."""
        cursor = self._now()
        for character in text:
            if character == " ":
                cursor += morse.dit_duration(self._wpm) * morse.WORD_SPACE_UNITS
                continue
            cursor += morse.character_duration(character, self._wpm)
            self._schedule(cursor, EchoEvent(character, from_paddle=True))
        self._schedule(cursor, StatusEvent(self._status_with(break_in=False)))

    def clear_buffer(self) -> None:
        self._clear_timeline()
        self._busy = False

    def ping(self) -> None:
        self._schedule(self._now(), StatusEvent(self._status))

    def drain_events(self) -> list[KeyerEvent]:
        now = self._now()
        events: list[KeyerEvent] = []
        while self._timeline and self._timeline[0][0] <= now:
            _, _, event = heapq.heappop(self._timeline)
            events.append(event)
            if isinstance(event, StatusEvent):
                self._status = event.status
                self._busy = event.status.busy
        return events

    # -- internals ------------------------------------------------------
    def _now(self) -> float:
        return self._clock()

    def _schedule(self, when: float, event: KeyerEvent) -> None:
        self._sequence += 1
        heapq.heappush(self._timeline, (when, self._sequence, event))

    def _clear_timeline(self) -> None:
        self._timeline.clear()

    def _status_with(
        self,
        *,
        busy: bool | None = None,
        break_in: bool | None = None,
    ) -> KeyerStatus:
        return KeyerStatus(
            raw=self._status.raw,
            wait=False,
            key_down=self._status.key_down,
            busy=self._status.busy if busy is None else busy,
            break_in=self._status.break_in if break_in is None else break_in,
            xoff=False,
            is_pushbutton=False,
        )
