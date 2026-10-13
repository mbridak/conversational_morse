"""Real K1EL WinKeyer USB backend using pyserial."""

from __future__ import annotations

import contextlib
import queue
import threading
import time
from collections.abc import Sequence
from typing import Final

import serial
from serial.tools import list_ports

from .. import morse
from . import protocol as proto
from .device import (
    KeyerDevice,
    KeyerEvent,
    StatusEvent,
    TxCompleteEvent,
    WinKeyerCodec,
)

READ_TIMEOUT: Final = 0.05
OPEN_RESPONSE_TIMEOUT: Final = 1.5
CHUNK_SETTLE: Final = 0.05
POLL_INTERVAL: Final = 0.2
COMPLETION_MARGIN: Final = 1.0


class KeyerError(RuntimeError):
    """Raised when the WinKeyer cannot be opened or communicated with."""


def list_serial_ports() -> list[str]:
    """Return the device paths of available serial ports."""
    return sorted(port.device for port in list_ports.comports())


def find_winkeyer_port() -> str | None:
    """Try to guess the WinKeyer port from USB descriptors."""
    keywords = ("wch", "ch340", "usbserial", "usbmodem", "ftdi", "winkeyer")
    for port in list_ports.comports():
        haystack = f"{port.device} {port.description} {port.manufacturer}".lower()
        if any(keyword in haystack for keyword in keywords):
            return str(port.device)
    return None


class WinKeyerDevice(KeyerDevice):
    """A WinKeyer connected over a serial port."""

    def __init__(self, port: str, baudrate: int = 1200) -> None:
        self._port = port
        self._baudrate = baudrate
        self._serial: serial.Serial | None = None
        self._codec = WinKeyerCodec()
        self._events: list[KeyerEvent] = []
        self._events_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._busy_lock = threading.Lock()
        self._busy = False
        self._wpm = 20
        self._revision: int | None = None
        self._running = False
        self._threads: list[threading.Thread] = []
        self._out_queue: queue.Queue[str | None] = queue.Queue()

    # -- properties -----------------------------------------------------
    @property
    def port(self) -> str:
        return self._port

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def revision(self) -> int | None:
        return self._revision

    @property
    def busy(self) -> bool:
        with self._busy_lock:
            return self._busy

    def _set_busy(self, value: bool) -> None:
        with self._busy_lock:
            self._busy = value

    # -- lifecycle ------------------------------------------------------
    def open(self) -> None:
        if self._serial is not None and self._serial.is_open:
            return
        try:
            self._serial = serial.Serial(
                self._port,
                self._baudrate,
                timeout=READ_TIMEOUT,
                write_timeout=1.0,
            )
        except serial.SerialException as exc:  # pragma: no cover - hardware
            raise KeyerError(f"could not open {self._port}: {exc}") from exc

        self._codec = WinKeyerCodec()
        with self._events_lock:
            self._events.clear()

        self._raw_write(proto.admin(proto.ADMIN_HOST_OPEN))
        self._revision = self._read_open_response()
        self._raw_write(proto.admin(proto.ADMIN_SET_WK2_MODE))

        self._running = True
        self._out_queue = queue.Queue()
        self._threads = [
            threading.Thread(target=self._reader_loop, daemon=True),
            threading.Thread(target=self._writer_loop, daemon=True),
            threading.Thread(target=self._poll_loop, daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        self._raw_write(proto.get_status())

    def close(self) -> None:
        self._running = False
        for thread in self._threads:
            thread.join(timeout=1.0)
        self._threads = []
        if self._serial is not None and self._serial.is_open:
            with contextlib.suppress(KeyerError):
                self._raw_write(proto.admin(proto.ADMIN_HOST_CLOSE))
            self._serial.close()
        self._serial = None
        self._set_busy(False)

    # -- configuration --------------------------------------------------
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
        self._raw_write(
            proto.set_mode(paddle_echo=paddle_echo, autospace=autospace),
        )
        self._raw_write(proto.set_sidetone(sidetone_index))
        self._raw_write(proto.set_ptt_lead_tail(lead_in_ms, tail_ms))
        self._raw_write(proto.set_wpm(wpm))

    def set_wpm(self, wpm: int) -> None:
        self._wpm = wpm
        self._raw_write(proto.set_wpm(wpm))

    def send_text(self, text: str) -> None:
        for chunk in proto.chunk_text(text):
            self._out_queue.put(chunk)
        self._out_queue.put(None)

    def clear_buffer(self) -> None:
        self._raw_write(proto.clear_buffer())
        while True:
            try:
                self._out_queue.get_nowait()
            except queue.Empty:
                break

    def ping(self) -> None:
        self._raw_write(proto.get_status())

    def drain_events(self) -> list[KeyerEvent]:
        with self._events_lock:
            events, self._events = self._events, []
        return events

    # -- serial helpers -------------------------------------------------
    def _raw_write(self, data: bytes) -> None:
        if self._serial is None or not self._serial.is_open:
            msg = "WinKeyer is not open"
            raise KeyerError(msg)
        with self._write_lock:
            try:
                self._serial.write(data)
            except serial.SerialException as exc:  # pragma: no cover - hardware
                raise KeyerError(f"serial write failed: {exc}") from exc

    def _read_open_response(self) -> int | None:
        if self._serial is None:
            return None
        deadline = time.monotonic() + OPEN_RESPONSE_TIMEOUT
        while time.monotonic() < deadline:
            data = self._serial.read(1)
            if not data:
                continue
            byte = int(data[0])
            if byte not in (0x00, 0xFF):
                return byte
        return None

    def _push_events(self, events: Sequence[KeyerEvent]) -> None:
        if not events:
            return
        with self._events_lock:
            self._events.extend(events)

    # -- threads --------------------------------------------------------
    def _reader_loop(self) -> None:
        while self._running and self._serial is not None:
            try:
                data = self._serial.read(1)
            except (serial.SerialException, TypeError):  # pragma: no cover
                break
            if not data:
                continue
            for event in self._codec.feed(data[0]):
                self._push_events([event])
                if isinstance(event, StatusEvent):
                    self._set_busy(event.status.busy)
        self._set_busy(False)

    def _writer_loop(self) -> None:
        while self._running:
            try:
                chunk = self._out_queue.get(timeout=POLL_INTERVAL)
            except queue.Empty:
                continue
            if chunk is None:
                self._set_busy(False)
                self._push_events([TxCompleteEvent()])
                continue
            try:
                self._raw_write(proto.encode_cw(chunk))
            except KeyerError:
                break
            self._await_chunk_complete(chunk)

    def _await_chunk_complete(self, chunk: str) -> None:
        saw_busy = False
        deadline = (
            time.monotonic()
            + morse.text_duration(chunk, self._wpm)
            + (COMPLETION_MARGIN)
        )
        while self._running and time.monotonic() < deadline:
            if self.busy:
                saw_busy = True
            elif saw_busy:
                time.sleep(CHUNK_SETTLE)
                if not self.busy:
                    return
            try:
                self._raw_write(proto.get_status())
            except KeyerError:
                return
            time.sleep(CHUNK_SETTLE)

    def _poll_loop(self) -> None:
        while self._running:
            time.sleep(POLL_INTERVAL)
            try:
                self._raw_write(proto.get_status())
            except KeyerError:
                break
