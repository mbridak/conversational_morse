"""Tests for the simulated keyer backend."""

from __future__ import annotations

import pytest

from conftest import FakeClock
from conversational_morse.keyer.device import (
    EchoEvent,
    StatusEvent,
    TxCompleteEvent,
)
from conversational_morse.keyer.simulator import SimulatedKeyer


def _open_simulator(clock: FakeClock, wpm: int = 20) -> SimulatedKeyer:
    keyer = SimulatedKeyer(clock)
    keyer.open()
    keyer.configure(
        wpm=wpm,
        sidetone_index=5,
        paddle_echo=True,
        autospace=True,
    )
    return keyer


def test_open_sets_revision(fake_clock: FakeClock) -> None:
    keyer = _open_simulator(fake_clock)
    assert keyer.is_open is True
    assert keyer.revision is not None


def test_send_text_echoes_each_character(fake_clock: FakeClock) -> None:
    keyer = _open_simulator(fake_clock)
    keyer.send_text("EE")
    fake_clock.advance(5.0)
    events = keyer.drain_events()
    echoes = [e.character for e in events if isinstance(e, EchoEvent)]
    assert echoes == ["E", "E"]


def test_send_text_sets_and_clears_busy(fake_clock: FakeClock) -> None:
    keyer = _open_simulator(fake_clock)
    keyer.send_text("PARIS")
    fake_clock.advance(0.01)
    keyer.drain_events()
    assert keyer.busy is True
    fake_clock.advance(10.0)
    keyer.drain_events()
    assert keyer.busy is False


def test_send_text_emits_tx_complete(fake_clock: FakeClock) -> None:
    keyer = _open_simulator(fake_clock)
    keyer.send_text("TEST")
    fake_clock.advance(10.0)
    events = keyer.drain_events()
    assert any(isinstance(e, TxCompleteEvent) for e in events)


def test_echoes_are_withheld_until_time_passes(fake_clock: FakeClock) -> None:
    keyer = _open_simulator(fake_clock)
    keyer.send_text("PARIS")
    events = keyer.drain_events()
    assert not any(isinstance(e, EchoEvent) for e in events)
    assert keyer.sent_text == ["PARIS"]


def test_simulated_paddle_echo_is_flagged(fake_clock: FakeClock) -> None:
    keyer = _open_simulator(fake_clock)
    keyer.simulate_paddle("CQ")
    fake_clock.advance(5.0)
    events = keyer.drain_events()
    echoes = [e for e in events if isinstance(e, EchoEvent)]
    assert [e.character for e in echoes] == ["C", "Q"]
    assert all(e.from_paddle for e in echoes)


def test_send_text_before_open_is_rejected(fake_clock: FakeClock) -> None:
    keyer = SimulatedKeyer(fake_clock)
    with pytest.raises(RuntimeError):
        keyer.send_text("TEST")


def test_clear_buffer_discards_pending_traffic(fake_clock: FakeClock) -> None:
    keyer = _open_simulator(fake_clock)
    keyer.send_text("PARIS")
    keyer.clear_buffer()
    fake_clock.advance(10.0)
    events = keyer.drain_events()
    assert not any(isinstance(e, EchoEvent) for e in events)
    assert not any(isinstance(e, TxCompleteEvent) for e in events)


def test_ping_emits_current_status(fake_clock: FakeClock) -> None:
    keyer = _open_simulator(fake_clock)
    keyer.ping()
    events = keyer.drain_events()
    assert any(isinstance(e, StatusEvent) for e in events)
