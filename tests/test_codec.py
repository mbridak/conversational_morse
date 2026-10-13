"""Tests for the WinKeyer incoming byte decoder."""

from __future__ import annotations

from conversational_morse.keyer import protocol as proto
from conversational_morse.keyer.device import (
    EchoEvent,
    PotEvent,
    StatusEvent,
    WinKeyerCodec,
)


def test_status_byte_is_decoded() -> None:
    codec = WinKeyerCodec()
    events = codec.feed(0xC4)  # tag 110 + busy
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, StatusEvent)
    assert event.status.busy is True
    assert event.status.break_in is False


def test_pot_byte_is_decoded() -> None:
    codec = WinKeyerCodec()
    events = codec.feed(0x80 | 35)
    assert events == [PotEvent(35)]


def test_echo_byte_is_classified_by_break_in() -> None:
    codec = WinKeyerCodec()
    codec.feed(0xC2)  # break-in active
    events = codec.feed(ord("K"))
    assert events == [EchoEvent("K", from_paddle=True)]


def test_echo_is_serial_when_break_in_low() -> None:
    codec = WinKeyerCodec()
    codec.feed(0xC0)
    events = codec.feed(ord("A"))
    assert events == [EchoEvent("A", from_paddle=False)]


def test_pushbutton_byte_preserves_operational_bits() -> None:
    codec = WinKeyerCodec()
    codec.feed(0xC4)  # busy, no break-in
    events = codec.feed(0xC8)  # pushbutton byte, bit3 set
    event = events[0]
    assert isinstance(event, StatusEvent)
    assert event.status.is_pushbutton is True
    assert event.status.busy is True  # not clobbered by PB3 bit
    assert event.status.pushbuttons == 0x08


def test_feed_ignores_ff_placeholder() -> None:
    codec = WinKeyerCodec()
    assert codec.feed(0xFF) == []


def test_status_tag_mask_matches_protocol() -> None:
    codec = WinKeyerCodec()
    events = codec.feed(proto.STATUS_TAG)
    assert isinstance(events[0], StatusEvent)
