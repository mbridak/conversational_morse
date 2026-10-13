"""WinKeyer host-mode protocol constants and helpers.

Values follow the K1EL Winkeyer2 IC Interface & Operation Manual (V23) and are
compatible with WinKeyer3 firmware. Admin command arguments are decimal values
as documented (for example ``11`` selects WK2 mode).
"""

from __future__ import annotations

import re
from typing import Final

# Admin commands: <00><nn>
ADMIN_CALIBRATE: Final = 0
ADMIN_RESET: Final = 1
ADMIN_HOST_OPEN: Final = 2
ADMIN_HOST_CLOSE: Final = 3
ADMIN_ECHO_TEST: Final = 4
ADMIN_GET_VALUES: Final = 7
ADMIN_SET_WK1_MODE: Final = 10
ADMIN_SET_WK2_MODE: Final = 11
ADMIN_DUMP_EEPROM: Final = 12
ADMIN_LOAD_EEPROM: Final = 13
ADMIN_SEND_STANDALONE_MESSAGE: Final = 14
ADMIN_LOAD_XMODE: Final = 15
ADMIN_SET_HIGH_BAUD: Final = 17
ADMIN_SET_LOW_BAUD: Final = 18

# Immediate command opcodes
CMD_SIDETONE: Final = 0x01
CMD_SPEED: Final = 0x02
CMD_WEIGHTING: Final = 0x03
CMD_PTT_LEAD_TAIL: Final = 0x04
CMD_SPEED_POT_SETUP: Final = 0x05
CMD_PAUSE: Final = 0x06
CMD_GET_POT: Final = 0x07
CMD_BACKSPACE: Final = 0x08
CMD_CLEAR_BUFFER: Final = 0x0A
CMD_KEY_IMMEDIATE: Final = 0x0B
CMD_FARNSWORTH: Final = 0x0D
CMD_SET_MODE: Final = 0x0E
CMD_LOAD_DEFAULTS: Final = 0x0F
CMD_SOFTWARE_PADDLE: Final = 0x14
CMD_GET_STATUS: Final = 0x15
CMD_POINTER: Final = 0x16
CMD_SET_RATIO: Final = 0x17

# Buffered commands
CMD_BUF_PTT: Final = 0x18
CMD_BUF_KEY: Final = 0x19
CMD_BUF_WAIT: Final = 0x1A
CMD_BUF_MERGE: Final = 0x1B
CMD_BUF_SPEED: Final = 0x1C
CMD_BUF_HSCW: Final = 0x1D
CMD_BUF_CANCEL_SPEED: Final = 0x1E
CMD_BUF_NOP: Final = 0x1F

# Software paddle arguments
PADDLE_UP: Final = 0
PADDLE_DIT: Final = 1
PADDLE_DAH: Final = 2
PADDLE_BOTH: Final = 3

# Mode register bits (CMD_SET_MODE)
MODE_PADDLE_ECHO: Final = 0x40
MODE_SERIAL_ECHO: Final = 0x04
MODE_AUTOSPACE: Final = 0x02
MODE_CONTEST_SPACING: Final = 0x01

# Status byte masks
STATUS_TAG_MASK: Final = 0xE0
STATUS_TAG: Final = 0xC0
STATUS_WAIT: Final = 0x10
STATUS_KEY_DOWN: Final = 0x08
STATUS_PUSHBUTTON_FLAG: Final = 0x08
STATUS_BUSY: Final = 0x04
STATUS_BREAK_IN: Final = 0x02
STATUS_XOFF: Final = 0x01

POT_BYTE_MASK: Final = 0x80

MAX_BUFFER_CHARS: Final = 120

# Characters the WinKeyer maps to standard prosigns. These are sent inside the
# wire text so prosigns are transmitted without an inter-character gap.
PROSIGN_CODES: Final[dict[str, str]] = {
    "AR": "+",
    "SK": ">",
    "BT": "=",
    "KN": ":",
    "AS": ";",
    "DN": "/",
    "RR": '"',
}

CODE_TO_PROSIGN: Final[dict[str, str]] = {
    code: name for name, code in PROSIGN_CODES.items()
}

_PROSIGN_PATTERN: Final = re.compile(
    r"\b(" + "|".join(PROSIGN_CODES) + r")\b",
)


def admin(command: int, *args: int) -> bytes:
    """Build an admin command: ``<00><command>`` plus any argument bytes."""
    if not 0 <= command <= 255:
        msg = "admin command out of range"
        raise ValueError(msg)
    return bytes([0x00, command, *args])


def set_wpm(wpm: int) -> bytes:
    if not 5 <= wpm <= 99:
        msg = "wpm must be between 5 and 99"
        raise ValueError(msg)
    return bytes([CMD_SPEED, wpm])


def set_sidetone(index: int, *, paddle_only: bool = False) -> bytes:
    if not 0 <= index <= 10:
        msg = "sidetone index must be between 0 and 10"
        raise ValueError(msg)
    value = index | (0x80 if paddle_only else 0x00)
    return bytes([CMD_SIDETONE, value])


def set_mode(
    *,
    paddle_echo: bool = True,
    serial_echo: bool = False,
    autospace: bool = True,
    contest_spacing: bool = False,
) -> bytes:
    value = 0
    if paddle_echo:
        value |= MODE_PADDLE_ECHO
    if serial_echo:
        value |= MODE_SERIAL_ECHO
    if autospace:
        value |= MODE_AUTOSPACE
    if contest_spacing:
        value |= MODE_CONTEST_SPACING
    return bytes([CMD_SET_MODE, value])


def set_ptt_lead_tail(lead_in_ms: int, tail_ms: int) -> bytes:
    lead = max(0, min(250, lead_in_ms)) // 10
    tail = max(0, min(250, tail_ms)) // 10
    return bytes([CMD_PTT_LEAD_TAIL, lead, tail])


def software_paddle(paddle: int) -> bytes:
    if paddle not in (PADDLE_UP, PADDLE_DIT, PADDLE_DAH, PADDLE_BOTH):
        msg = "invalid software paddle value"
        raise ValueError(msg)
    return bytes([CMD_SOFTWARE_PADDLE, paddle])


def clear_buffer() -> bytes:
    return bytes([CMD_CLEAR_BUFFER])


def get_status() -> bytes:
    return bytes([CMD_GET_STATUS])


def get_speed_pot() -> bytes:
    return bytes([CMD_GET_POT])


def encode_cw(text: str) -> bytes:
    """Encode human readable CW text for transmission.

    Known prowords (``AR``, ``SK``, ``BT``, ``KN``, ``AS``, ``DN``, ``RR``) are
    replaced with the WinKeyer mapped characters so they are sent as prosigns.
    """

    def _replace(match: re.Match[str]) -> str:
        return PROSIGN_CODES[match.group(1)]

    return _PROSIGN_PATTERN.sub(_replace, text.upper()).encode("ascii", "replace")


def humanize_cw(wire: str) -> str:
    """Convert wire prosign codes back into readable prowords for display."""
    return "".join(CODE_TO_PROSIGN.get(char, char) for char in wire)


def chunk_text(text: str, limit: int = MAX_BUFFER_CHARS) -> list[str]:
    """Split text into chunks no longer than ``limit`` characters.

    Splitting prefers word boundaries so the keyer never receives a truncated
    word inside a single buffer fill.
    """
    if limit <= 0:
        msg = "limit must be positive"
        raise ValueError(msg)
    chunks: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(word) > limit:
            chunks.append(word[:limit])
            word = word[limit:]
        current = word
    if current:
        chunks.append(current)
    return chunks
