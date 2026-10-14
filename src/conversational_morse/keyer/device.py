"""Keyer device abstraction, events and the incoming byte decoder."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from . import protocol as proto


@dataclass(frozen=True)
class KeyerStatus:
    """Decoded WinKeyer status byte."""

    raw: int
    wait: bool
    key_down: bool
    busy: bool
    break_in: bool
    xoff: bool
    is_pushbutton: bool
    pushbuttons: int = 0

    @classmethod
    def from_raw(cls, raw: int) -> KeyerStatus:
        is_pushbutton = bool(raw & proto.STATUS_PUSHBUTTON_FLAG)
        return cls(
            raw=raw,
            wait=bool(raw & proto.STATUS_WAIT) and not is_pushbutton,
            key_down=bool(raw & proto.STATUS_KEY_DOWN) and not is_pushbutton,
            busy=bool(raw & proto.STATUS_BUSY) and not is_pushbutton,
            break_in=bool(raw & proto.STATUS_BREAK_IN) and not is_pushbutton,
            xoff=bool(raw & proto.STATUS_XOFF) and not is_pushbutton,
            is_pushbutton=is_pushbutton,
            pushbuttons=raw & 0x0F if is_pushbutton else 0,
        )

    @classmethod
    def from_pushbutton(cls, raw: int, previous: KeyerStatus) -> KeyerStatus:
        """Build a pushbutton report without disturbing operational bits."""
        return cls(
            raw=raw,
            wait=previous.wait,
            key_down=previous.key_down,
            busy=previous.busy,
            break_in=previous.break_in,
            xoff=previous.xoff,
            is_pushbutton=True,
            pushbuttons=raw & 0x0F,
        )

    @classmethod
    def empty(cls) -> KeyerStatus:
        return cls(
            raw=0,
            wait=False,
            key_down=False,
            busy=False,
            break_in=False,
            xoff=False,
            is_pushbutton=False,
        )


@dataclass(frozen=True)
class StatusEvent:
    status: KeyerStatus


@dataclass(frozen=True)
class PotEvent:
    value: int


@dataclass(frozen=True)
class EchoEvent:
    character: str
    from_paddle: bool


@dataclass(frozen=True)
class TxCompleteEvent:
    """Emitted when a transmission requested by the host has finished."""


KeyerEvent = StatusEvent | PotEvent | EchoEvent | TxCompleteEvent


class WinKeyerCodec:
    """Incrementally decode bytes received from a WinKeyer."""

    def __init__(self) -> None:
        self.status = KeyerStatus.empty()

    def feed(self, byte: int) -> list[KeyerEvent]:
        if byte == 0xFF:
            return []
        if (byte & proto.STATUS_TAG_MASK) == proto.STATUS_TAG:
            status = KeyerStatus.from_raw(byte)
            if status.is_pushbutton:
                status = KeyerStatus.from_pushbutton(byte, self.status)
            self.status = status
            return [StatusEvent(status)]
        if byte & proto.POT_BYTE_MASK:
            return [PotEvent(byte & ~proto.POT_BYTE_MASK)]
        from_paddle = self.status.break_in
        return [EchoEvent(chr(byte), from_paddle)]


class KeyerDevice(ABC):
    """Common interface implemented by the real and simulated keyers."""

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Whether the device is currently open."""

    @property
    @abstractmethod
    def revision(self) -> int | None:
        """Firmware revision code reported on open, if known."""

    @property
    @abstractmethod
    def busy(self) -> bool:
        """Whether the keyer is currently sending Morse."""

    @abstractmethod
    def open(self) -> None:
        """Open the device and apply the host-mode initialisation sequence."""

    @abstractmethod
    def close(self) -> None:
        """Close the device, returning it to standalone mode where relevant."""

    @abstractmethod
    def configure(
        self,
        *,
        wpm: int,
        sidetone_index: int,
        paddle_echo: bool,
        autospace: bool,
        lead_in_ms: int = 10,
        tail_ms: int = 10,
        sidetone_volume: str = "normal",
    ) -> None:
        """Apply operating parameters to the keyer."""

    @abstractmethod
    def set_sidetone_volume(self, level: str) -> None:
        """Set the sidetone volume level (WinKeyer 3.1 and later)."""

    @abstractmethod
    def set_wpm(self, wpm: int) -> None:
        """Change the sending speed in words per minute."""

    @abstractmethod
    def send_text(self, text: str) -> None:
        """Queue text to be sent as Morse."""

    @abstractmethod
    def clear_buffer(self) -> None:
        """Abort any queued Morse and empty the input buffer."""

    @abstractmethod
    def drain_events(self) -> list[KeyerEvent]:
        """Return and clear all pending events (non-blocking)."""

    @abstractmethod
    def ping(self) -> None:
        """Request a status byte from the keyer."""
