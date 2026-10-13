"""International Morse code tables and CW timing maths.

The WinKeyer performs the actual Morse encoding, so this module is used for
timing estimates (mainly by the simulator) and for rendering dots and dashes
back to the operator in the user interface.
"""

from __future__ import annotations

from typing import Final

TEXT_TO_MORSE: Final[dict[str, str]] = {
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
    "0": "-----",
    "1": ".----",
    "2": "..---",
    "3": "...--",
    "4": "....-",
    "5": ".....",
    "6": "-....",
    "7": "--...",
    "8": "---..",
    "9": "----.",
    ".": ".-.-.-",
    ",": "--..--",
    "?": "..--..",
    "/": "-..-.",
    "=": "-...-",
    "+": ".-.-.",
    "-": "-....-",
    "@": ".--.-.",
    ":": "---...",
    ";": "-.-.-.",
    '"': ".-..-.",
    ">": "...-.-",
}

WORD_SPACE_UNITS: Final = 7.0
LETTER_SPACE_UNITS: Final = 3.0
INTRA_CHARACTER_UNITS: Final = 1.0
DOT_UNITS: Final = 1.0
DAH_UNITS: Final = 3.0


def dit_duration(wpm: int) -> float:
    """Return the duration of one dit in seconds for a given speed."""
    if wpm <= 0:
        msg = "wpm must be positive"
        raise ValueError(msg)
    return 1.2 / wpm


def character_duration(character: str, wpm: int) -> float:
    """Duration in seconds to send a single character including letter space."""
    morse = TEXT_TO_MORSE.get(character.upper())
    if morse is None:
        return dit_duration(wpm) * LETTER_SPACE_UNITS
    unit = dit_duration(wpm)
    element_time = sum(DOT_UNITS if e == "." else DAH_UNITS for e in morse)
    gaps = INTRA_CHARACTER_UNITS * (len(morse) - 1)
    return unit * (element_time + gaps + LETTER_SPACE_UNITS)


def text_duration(text: str, wpm: int) -> float:
    """Approximate duration in seconds to send a block of text."""
    total = 0.0
    for character in text.strip():
        if character == " ":
            total += dit_duration(wpm) * WORD_SPACE_UNITS
        else:
            total += character_duration(character, wpm)
    return total


def to_morse(text: str) -> str:
    """Render text as a spaced dot/dash string for display purposes."""
    chunks: list[str] = []
    for character in text.upper():
        if character == " ":
            chunks.append("/")
        elif character in TEXT_TO_MORSE:
            chunks.append(TEXT_TO_MORSE[character])
    return " ".join(chunks)
