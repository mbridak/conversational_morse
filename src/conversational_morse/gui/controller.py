"""Qt controller that connects a keyer device to the QSO engine."""

from __future__ import annotations

import random
import time
from collections import deque
from collections.abc import Callable
from enum import Enum

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..config import KeyerConfig, StationConfig
from ..keyer import (
    EchoEvent,
    KeyerDevice,
    KeyerError,
    KeyerStatus,
    PotEvent,
    SimulatedKeyer,
    StatusEvent,
    TxCompleteEvent,
    WinKeyerDevice,
)
from ..qso import (
    CopyReport,
    QsoEngine,
    QsoLength,
    QsoMode,
    Speaker,
    random_dx_station,
)

POLL_INTERVAL_MS = 50
MAX_RX_BUFFER = 80


class SessionState(Enum):
    """High level state of the practice session."""

    DISCONNECTED = "disconnected"
    IDLE = "idle"
    DX_SENDING = "dx_sending"
    AWAITING_USER = "awaiting_user"
    USER_SENDING = "user_sending"
    FINISHED = "finished"


class SessionController(QObject):
    """Owns the keyer device and advances the conversation."""

    log_message = pyqtSignal(str, str)
    status_changed = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)
    state_changed = pyqtSignal()
    user_buffer_changed = pyqtSignal(str)
    copy_report_ready = pyqtSignal(object)
    error = pyqtSignal(str)
    session_finished = pyqtSignal()

    def __init__(
        self,
        config: KeyerConfig,
        parent: QObject | None = None,
        device_factory: Callable[[KeyerConfig], KeyerDevice] | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._device_factory = device_factory
        self._device: KeyerDevice | None = None
        self._engine: QsoEngine | None = None
        self._state = SessionState.DISCONNECTED
        self._pending_tx: deque[Callable[[], None]] = deque()
        self._rx_buffer = ""
        self._last_paddle_time = 0.0
        self._rng = random.Random()

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    # -- properties -----------------------------------------------------
    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def device(self) -> KeyerDevice | None:
        return self._device

    @property
    def engine(self) -> QsoEngine | None:
        return self._engine

    @property
    def user_buffer(self) -> str:
        return self._rx_buffer

    @property
    def is_connected(self) -> bool:
        return self._device is not None and self._device.is_open

    # -- connection -----------------------------------------------------
    def connect_keyer(self) -> None:
        try:
            device = self._build_device()
            device.open()
            device.configure(
                wpm=self._config.wpm,
                sidetone_index=self._config.sidetone_index,
                paddle_echo=self._config.paddle_echo,
                autospace=self._config.autospace,
                lead_in_ms=self._config.lead_in_ms,
                tail_ms=self._config.tail_ms,
            )
        except KeyerError as exc:
            self.error.emit(str(exc))
            return
        self._device = device
        self._state = SessionState.IDLE
        self._timer.start()
        backend = device.port if isinstance(device, WinKeyerDevice) else "simulator"
        revision = device.revision
        self.status_changed.emit(
            f"Connected to {backend} (rev {revision}) at {self._config.wpm} WPM",
        )
        self.connection_changed.emit(True)
        self.state_changed.emit()

    def disconnect_keyer(self) -> None:
        self._timer.stop()
        if self._device is not None:
            self._device.close()
        self._device = None
        self._engine = None
        self._state = SessionState.DISCONNECTED
        self.status_changed.emit("Disconnected")
        self.connection_changed.emit(False)
        self.state_changed.emit()

    def _build_device(self) -> KeyerDevice:
        if self._device_factory is not None:
            return self._device_factory(self._config)
        if self._config.use_simulator or not self._config.port:
            return SimulatedKeyer()
        return WinKeyerDevice(self._config.port, self._config.baudrate)

    def set_wpm(self, wpm: int) -> None:
        self._config.wpm = wpm
        if self._device is not None and self._device.is_open:
            self._device.set_wpm(wpm)

    # -- session --------------------------------------------------------
    def start_qso(
        self, mode: QsoMode, length: QsoLength, station: StationConfig
    ) -> None:
        if not self.is_connected:
            self.error.emit("Connect to the keyer before starting a QSO.")
            return
        dx = random_dx_station(self._rng)
        self._engine = QsoEngine.create(station, dx, mode, length, rng=self._rng)
        self.log_message.emit(
            "system",
            f"New QSO with {dx.callsign} ({dx.name}, {dx.qth})",
        )
        self._play_current()

    def _play_current(self) -> None:
        engine = self._engine
        if engine is None:
            return
        if engine.is_finished:
            self._finish_session()
            return
        turn = engine.current_turn
        if turn is None:
            self._finish_session()
            return
        if turn.speaker is Speaker.DX:
            engine.record(Speaker.DX, turn.text)
            self.log_message.emit("dx", turn.text)
            self._state = SessionState.DX_SENDING
            self.state_changed.emit()
            assert self._device is not None
            self._device.send_text(turn.text)
            self._pending_tx.append(self._advance)
        else:
            self._rx_buffer = ""
            self._state = SessionState.AWAITING_USER
            self.user_buffer_changed.emit("")
            if turn.hint:
                self.log_message.emit("hint", turn.hint)
            self.state_changed.emit()

    def send_for_me(self) -> None:
        engine = self._engine
        if engine is None or not engine.is_user_turn:
            return
        turn = engine.current_turn
        if turn is None:
            return
        engine.record(Speaker.USER, turn.text)
        self.log_message.emit("user", turn.text)
        self._rx_buffer = ""
        self._transmit_or_advance(turn.text, transmit=True)

    def submit_typed(self, text: str, *, transmit: bool = True) -> None:
        """Submit an operator turn typed on the keyboard."""
        engine = self._engine
        if engine is None or not engine.is_user_turn or not text.strip():
            return
        report = engine.grade_current(text)
        engine.record(Speaker.USER, text)
        self.log_message.emit("user", text)
        self.copy_report_ready.emit(report)
        self._rx_buffer = ""
        self._transmit_or_advance(text, transmit=transmit)

    def end_over(self) -> None:
        self._complete_user_turn()

    def _complete_user_turn(self) -> None:
        engine = self._engine
        if engine is None or not engine.is_user_turn:
            return
        text = self._rx_buffer.strip()
        if not text:
            return
        report = engine.grade_current(text)
        engine.record(Speaker.USER, text)
        self.log_message.emit("user", text)
        self.copy_report_ready.emit(report)
        self._rx_buffer = ""
        self._advance()

    def _transmit_or_advance(self, text: str, *, transmit: bool) -> None:
        device = self._device
        if transmit and device is not None and device.is_open:
            self._state = SessionState.USER_SENDING
            self.state_changed.emit()
            device.send_text(text)
            self._pending_tx.append(self._advance)
        else:
            self._advance()

    def _advance(self) -> None:
        engine = self._engine
        if engine is None:
            return
        engine.advance()
        self._play_current()

    def _finish_session(self) -> None:
        self._state = SessionState.FINISHED
        self.log_message.emit("system", "QSO complete. 73!")
        self.state_changed.emit()
        self.session_finished.emit()

    def abort_session(self) -> None:
        if self._device is not None and self._device.is_open:
            self._device.clear_buffer()
        self._engine = None
        self._pending_tx.clear()
        self._rx_buffer = ""
        self._state = SessionState.IDLE
        self.user_buffer_changed.emit("")
        self.log_message.emit("system", "QSO aborted.")
        self.state_changed.emit()

    # -- event handling -------------------------------------------------
    def _poll(self) -> None:
        device = self._device
        if device is None:
            return
        for event in device.drain_events():
            if isinstance(event, EchoEvent):
                self._on_echo(event.character, event.from_paddle)
            elif isinstance(event, TxCompleteEvent):
                self._on_tx_complete()
            elif isinstance(event, StatusEvent):
                self._on_status(event.status)
            elif isinstance(event, PotEvent):
                self.status_changed.emit(f"Speed pot: {event.value} WPM")
        self._check_user_idle()

    def _on_echo(self, character: str, from_paddle: bool) -> None:
        """Capture an echoed Morse letter as operator input.

        Serial echo is disabled in the mode byte we program, so any echo the
        keyer produces is the operator keying the paddles. The WinKeyer only
        sets the break-in bit for a short window while a letter is being sent,
        so we do not rely on ``from_paddle`` to tell the two sources apart.
        """
        if not character.isprintable():
            return
        self._last_paddle_time = time.monotonic()
        if self._state in (SessionState.IDLE, SessionState.AWAITING_USER):
            self._rx_buffer = (self._rx_buffer + character)[-MAX_RX_BUFFER:]
            self.user_buffer_changed.emit(self._rx_buffer)

    def _on_status(self, status: KeyerStatus) -> None:
        if status.break_in:
            self._last_paddle_time = time.monotonic()

    def _on_tx_complete(self) -> None:
        if self._pending_tx:
            action = self._pending_tx.popleft()
            action()

    def _check_user_idle(self) -> None:
        if self._state is not SessionState.AWAITING_USER:
            return
        if not self._rx_buffer:
            return
        if time.monotonic() - self._last_paddle_time >= self._config.over_idle_seconds:
            self._complete_user_turn()

    def configure_settings(self, config: KeyerConfig) -> None:
        self._config = config


__all__ = ["SessionController", "SessionState", "CopyReport"]
