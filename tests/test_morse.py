"""Tests for Morse timing helpers."""

from __future__ import annotations

import pytest

from conversational_morse import morse


def test_dit_duration_at_20_wpm() -> None:
    assert morse.dit_duration(20) == pytest.approx(0.06)


def test_dit_duration_rejects_zero() -> None:
    with pytest.raises(ValueError):
        morse.dit_duration(0)


def test_character_duration_scales_inversely_with_speed() -> None:
    assert morse.character_duration("E", 10) > morse.character_duration("E", 20)


def test_text_duration_includes_word_spaces() -> None:
    one_word = morse.text_duration("PARIS", 20)
    two_words = morse.text_duration("PARIS PARIS", 20)
    assert two_words > one_word * 2


def test_to_morse_renders_letters_and_spaces() -> None:
    assert morse.to_morse("ET") == ". -"
    assert morse.to_morse("E T") == ". / -"
