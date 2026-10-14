"""Tests for the Qt session controller driving a simulated keyer."""

from __future__ import annotations

import types
from collections.abc import Iterator

import pytest

from conftest import FakeClock
from conversational_morse.config import KeyerConfig, StationConfig
from conversational_morse.gui import controller as ctrl_mod
from conversational_morse.gui.controller import SessionController, SessionState
from conversational_morse.keyer.simulator import SimulatedKeyer
from conversational_morse.qso import QsoLength, QsoMode, Speaker

STATION = StationConfig(callsign="W6ABC", name="JIM", qth="FRESNO, CA")


def state_of(controller: SessionController) -> SessionState:
    """Read the session state without triggering mypy literal narrowing."""
    return controller.state


@pytest.fixture
def controller(
    qapp: object,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[SessionController]:
    monkeypatch.setattr(
        ctrl_mod,
        "time",
        types.SimpleNamespace(monotonic=fake_clock),
    )
    device = SimulatedKeyer(fake_clock)
    keyer_config = KeyerConfig(wpm=20, use_simulator=True)
    ctrl = SessionController(
        keyer_config,
        device_factory=lambda _config: device,
    )
    ctrl.connect_keyer()
    yield ctrl
    ctrl.disconnect_keyer()


def test_connect_reports_connected(controller: SessionController) -> None:
    assert controller.is_connected is True
    assert state_of(controller) is SessionState.IDLE


def test_connect_applies_configured_sidetone_volume(
    qapp: object,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ctrl_mod,
        "time",
        types.SimpleNamespace(monotonic=fake_clock),
    )
    device = SimulatedKeyer(fake_clock)
    ctrl = SessionController(
        KeyerConfig(wpm=20, use_simulator=True, sidetone_volume="low"),
        device_factory=lambda _config: device,
    )
    try:
        ctrl.connect_keyer()
        assert device.sidetone_volume == "low"
    finally:
        ctrl.disconnect_keyer()


def test_set_sidetone_volume_updates_live_device(
    controller: SessionController,
) -> None:
    controller.set_sidetone_volume("low")
    device = controller.device
    assert isinstance(device, SimulatedKeyer)
    assert device.sidetone_volume == "low"


def test_start_qso_sends_dx_cq_and_waits(
    controller: SessionController,
    fake_clock: FakeClock,
) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    device = controller.device
    assert isinstance(device, SimulatedKeyer)
    assert device.sent_text[0].startswith("CQ CQ DE")
    assert state_of(controller) is SessionState.DX_SENDING

    fake_clock.advance(120.0)
    controller._poll()
    assert state_of(controller) is SessionState.AWAITING_USER


def test_paddle_input_is_captured_and_graded(
    controller: SessionController,
    fake_clock: FakeClock,
) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    fake_clock.advance(120.0)
    controller._poll()

    engine = controller.engine
    assert engine is not None
    answer = engine.model_answer()
    device = controller.device
    assert isinstance(device, SimulatedKeyer)
    device.simulate_paddle(answer)
    fake_clock.advance(60.0)
    controller._poll()
    assert controller.user_buffer.replace(" ", "") == answer.replace(" ", "")

    fake_clock.advance(10.0)
    controller._poll()
    # The over is submitted on idle and the DX station takes the next turn.
    assert state_of(controller) is SessionState.DX_SENDING


def test_typed_submit_advances_turn(
    controller: SessionController,
    fake_clock: FakeClock,
) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    fake_clock.advance(120.0)
    controller._poll()
    assert state_of(controller) is SessionState.AWAITING_USER

    engine = controller.engine
    assert engine is not None
    controller.submit_typed(engine.model_answer())
    # The over is keyed through the WinKeyer before the DX responds.
    assert state_of(controller) is SessionState.USER_SENDING
    fake_clock.advance(120.0)
    controller._poll()
    assert state_of(controller) is SessionState.DX_SENDING


def test_send_for_me_uses_model_answer(controller: SessionController) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    # Finish the DX CQ turn without waiting on the clock.
    controller._on_tx_complete()
    assert state_of(controller) is SessionState.AWAITING_USER
    controller.send_for_me()
    assert state_of(controller) is SessionState.USER_SENDING
    controller._on_tx_complete()
    assert state_of(controller) in (SessionState.DX_SENDING, SessionState.FINISHED)


def test_echo_is_captured_even_if_break_in_was_missed(
    controller: SessionController,
) -> None:
    """Serial echo is disabled, so an echo without break-in is still paddle input."""
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller._on_tx_complete()  # finish the DX CQ turn
    assert state_of(controller) is SessionState.AWAITING_USER
    controller._on_echo("K", from_paddle=False)
    controller._on_echo("N", from_paddle=True)
    assert controller.user_buffer == "KN"


def test_paddle_echo_is_captured_before_a_qso_starts(
    controller: SessionController,
) -> None:
    """Keying paddles while connected (no active QSO) gives immediate feedback."""
    assert state_of(controller) is SessionState.IDLE
    controller._on_echo("C", from_paddle=True)
    controller._on_echo("Q", from_paddle=True)
    assert controller.user_buffer == "CQ"


def test_abort_returns_to_idle(controller: SessionController) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller.abort_session()
    assert state_of(controller) is SessionState.IDLE
    assert controller.engine is None


def test_conversation_can_run_to_completion(
    controller: SessionController,
) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    engine = controller.engine
    assert engine is not None
    for _ in range(len(engine.turns)):
        engine.advance()
    assert engine.is_finished is True


def test_incomplete_over_asks_for_repeat_without_advancing(
    controller: SessionController,
) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller._on_tx_complete()  # DX CQ finishes -> the operator's turn
    assert state_of(controller) is SessionState.AWAITING_USER
    engine = controller.engine
    assert engine is not None
    index_before = engine.index

    # Send only the DX station's call, so the check must fail.
    controller.submit_typed(engine.dx_callsign)
    assert state_of(controller) is SessionState.USER_SENDING
    controller._on_tx_complete()  # operator over keyed -> DX repeat request
    assert state_of(controller) is SessionState.DX_SENDING
    controller._on_tx_complete()  # repeat request sent -> same turn again
    assert state_of(controller) is SessionState.AWAITING_USER
    assert engine.index == index_before


def test_incomplete_over_continues_after_max_attempts(
    controller: SessionController,
) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller._on_tx_complete()
    engine = controller.engine
    assert engine is not None
    start_index = engine.index

    for attempt in range(1, ctrl_mod.MAX_OVER_ATTEMPTS + 1):
        controller.submit_typed(engine.dx_callsign)  # never sends your own call
        controller._on_tx_complete()  # finish keying the over
        if attempt < ctrl_mod.MAX_OVER_ATTEMPTS:
            assert state_of(controller) is SessionState.DX_SENDING
            controller._on_tx_complete()  # repeat request completes
            assert state_of(controller) is SessionState.AWAITING_USER
            assert engine.index == start_index
        else:
            assert engine.index == start_index + 1
            assert state_of(controller) is SessionState.DX_SENDING


def test_advisory_mode_advances_on_incomplete_over(
    controller: SessionController,
) -> None:
    config = KeyerConfig(wpm=20, use_simulator=True, require_correct_copy=False)
    controller.configure_settings(config)
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller._on_tx_complete()
    engine = controller.engine
    assert engine is not None
    start_index = engine.index

    controller.submit_typed(engine.dx_callsign)  # incomplete, but checks are off
    controller._on_tx_complete()
    assert engine.index == start_index + 1
    assert state_of(controller) is SessionState.DX_SENDING


def test_correct_cq_answer_advances(
    controller: SessionController,
) -> None:
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller._on_tx_complete()
    engine = controller.engine
    assert engine is not None
    start_index = engine.index

    controller.submit_typed(engine.model_answer())
    controller._on_tx_complete()
    assert engine.index == start_index + 1
    assert state_of(controller) is SessionState.DX_SENDING


def test_partial_call_asks_dx_to_repeat_callsign(
    controller: SessionController,
) -> None:
    """Answering a CQ with a partial call plus '?' makes the DX send its call."""
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller._on_tx_complete()  # DX CQ finishes -> operator's answer turn
    engine = controller.engine
    assert engine is not None
    device = controller.device
    assert isinstance(device, SimulatedKeyer)
    index_before = engine.index

    controller.submit_typed("W6?")
    controller._on_tx_complete()  # key the request -> DX repeats its call
    assert state_of(controller) is SessionState.DX_SENDING
    assert device.sent_text[-1] == f"{engine.dx_callsign} {engine.dx_callsign}"

    controller._on_tx_complete()  # repeat finishes -> same turn again
    assert state_of(controller) is SessionState.AWAITING_USER
    assert engine.index == index_before


def test_detail_repeat_request_resends_info(
    controller: SessionController,
) -> None:
    """A later 'QTH?' makes the DX resend that detail and reopens the turn."""
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller._on_tx_complete()  # DX CQ -> answer turn
    engine = controller.engine
    assert engine is not None
    controller.submit_typed(engine.model_answer())
    controller._on_tx_complete()  # answer keyed -> DX P1
    controller._on_tx_complete()  # P1 sent -> operator's P1 turn
    assert state_of(controller) is SessionState.AWAITING_USER
    device = controller.device
    assert isinstance(device, SimulatedKeyer)
    index_before = engine.index

    controller.submit_typed("QTH?")
    controller._on_tx_complete()  # request keyed -> DX resends the QTH
    assert state_of(controller) is SessionState.DX_SENDING
    p1 = next(
        turn
        for turn in engine.turns
        if turn.label == "P1" and turn.speaker is Speaker.DX
    )
    assert p1.repeat_phrases["QTH"] in device.sent_text[-1]

    controller._on_tx_complete()  # resend finishes -> same turn again
    assert state_of(controller) is SessionState.AWAITING_USER
    assert engine.index == index_before


def test_repeat_request_does_not_advance_past_the_turn(
    controller: SessionController,
) -> None:
    """Even without 'require correct copy', '?' is handled as a repeat."""
    config = KeyerConfig(wpm=20, use_simulator=True, require_correct_copy=False)
    controller.configure_settings(config)
    controller.start_qso(QsoMode.DX_CALLS_CQ, QsoLength.SHORT, STATION)
    controller._on_tx_complete()
    engine = controller.engine
    assert engine is not None
    index_before = engine.index

    controller.submit_typed("W6?")
    controller._on_tx_complete()
    controller._on_tx_complete()
    assert engine.index == index_before
    assert state_of(controller) is SessionState.AWAITING_USER
