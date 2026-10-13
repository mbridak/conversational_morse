"""Tests for WinKeyer protocol encoding helpers."""

from __future__ import annotations

import pytest

from conversational_morse.keyer import protocol as proto


def test_admin_host_open() -> None:
    assert proto.admin(proto.ADMIN_HOST_OPEN) == bytes([0x00, 0x02])


def test_admin_wk2_mode_is_decimal_eleven() -> None:
    assert proto.admin(proto.ADMIN_SET_WK2_MODE) == bytes([0x00, 0x0B])


def test_set_wpm_round_trip() -> None:
    assert proto.set_wpm(25) == bytes([0x02, 25])


@pytest.mark.parametrize("wpm", [4, 100])
def test_set_wpm_rejects_out_of_range(wpm: int) -> None:
    with pytest.raises(ValueError):
        proto.set_wpm(wpm)


def test_set_sidetone_paddle_only_flag() -> None:
    assert proto.set_sidetone(5) == bytes([0x01, 0x05])
    assert proto.set_sidetone(5, paddle_only=True) == bytes([0x01, 0x85])


def test_set_mode_combines_bits() -> None:
    assert proto.set_mode(paddle_echo=True, autospace=True) == bytes([0x0E, 0x42])
    assert proto.set_mode(
        paddle_echo=False,
        serial_echo=True,
        autospace=False,
    ) == bytes([0x0E, 0x04])


def test_set_ptt_lead_tail_uses_ten_ms_steps() -> None:
    assert proto.set_ptt_lead_tail(30, 50) == bytes([0x04, 3, 5])


def test_software_paddle_rejects_bad_value() -> None:
    with pytest.raises(ValueError):
        proto.software_paddle(9)


def test_encode_cw_converts_prosigns() -> None:
    encoded = proto.encode_cw("OK HW? AR").decode()
    assert encoded.endswith("+")


def test_encode_cw_leaves_plain_words_alone() -> None:
    assert proto.encode_cw("NAME JIM").decode() == "NAME JIM"


def test_encode_cw_does_not_touch_substrings() -> None:
    # "MARK" contains "AR" but must not become a prosign.
    assert proto.encode_cw("MARK").decode() == "MARK"


def test_humanize_cw_reverses_codes() -> None:
    assert proto.humanize_cw("TU >") == "TU SK"


def test_chunk_text_respects_limit_on_word_boundaries() -> None:
    text = " ".join(["WORD"] * 20)
    chunks = proto.chunk_text(text, limit=21)
    assert all(len(chunk) <= 21 for chunk in chunks)
    assert " ".join(chunks) == text


def test_chunk_text_splits_very_long_words() -> None:
    chunks = proto.chunk_text("X" * 250, limit=100)
    assert [len(chunk) for chunk in chunks] == [100, 100, 50]
