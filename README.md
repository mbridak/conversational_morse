# Conversational Morse

[![PyPI](https://img.shields.io/pypi/v/conversational-morse.svg)](https://pypi.org/project/conversational-morse/)
[![Python versions](https://img.shields.io/pypi/pyversions/conversational-morse.svg)](https://pypi.org/project/conversational-morse/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/mbridak/conversational-morse/blob/main/LICENSE)

A PyQt6 desktop application that simulates a realistic amateur-radio CW (Morse
code) contact so you can learn and practise sending and copying Morse. It drives
a **K1EL WinKeyer USB** for both the code that the "other station" sends and the
code you key on your paddles.

You can be either side of the contact:

- **Call CQ yourself** and work a station that answers you, or
- **Answer a CQ** sent by the simulated station.

The conversation follows the standard exchange documented in the CW QSO Protocol
sheet (RST / QTH / name, then rig / antenna / weather, then age / years licensed /
key, and finally the 73 / SK sign-off with the closing two dits).

## Why the WinKeyer does the Morse

The WinKeyer generates perfectly timed Morse and, importantly, can **echo every
character you key on the paddles back to the computer**. That is how the
application "hears" your sending, logs it and grades how much of the required
information you copied.

## Requirements

- Python 3.12 or newer.
- A K1EL WinKeyer (WKUSB or similar) and, for sending, a set of paddles. The
  built-in simulator lets you practise with no hardware at all.
- On macOS the WinKeyer appears as a `/dev/cu.usbserial-*` device.

## Install

Install the released package from [PyPI](https://pypi.org/project/conversational-morse/):

```sh
uv tool install conversational-morse
```

or into the active virtual environment:

```sh
pip install conversational-morse
```

Then launch it:

```sh
conversational-morse
```

To run from a source checkout instead (development):

```sh
uv sync
uv run conversational-morse   # or: uv run python main.py
```

## Using the application

1. **Connect.** Pick the WinKeyer port (the app tries to guess it), choose a
   speed and sidetone, then press **Connect**. If you have no hardware attached,
   tick **Use simulator** - the whole QSO flow still works and you can type your
   overs instead of keying them.
2. **Set up your station.** Press **Station setup...** and enter your callsign,
   name, QTH and the details used to build your side of the exchange. Your
   settings are saved to `~/.config/conversational_morse/config.json`.
3. **Start a contact** with either **I will call CQ** or **Answer the DX
   station**, and choose how long the contact should be (short exchange, medium
   or a full rag-chew).
4. **Listen** while the DX station sends, then **send your over**:
   - Key it on the paddles. Your sending appears live in
     *Received from paddles* and is submitted automatically after a short pause
     (configurable), or when you press **End over**. You can test your paddles
     as soon as the keyer is connected: keyed characters appear even before you
     start a contact.
   - Or type the text in the box at the bottom and press Enter; it is keyed
     through the WinKeyer so you hear it, and it counts as your over.
   - Or press **Send the model answer for me** to hear a correct example.
5. After each of your overs you get a **copy report** showing which required
   pieces of information were present.

### Correct-copy checking

With **Require correct copy** enabled (the default), the DX station checks each
of your overs before the contact moves on. Every portion is checked — the CQ
answer must carry your own callsign (that is all you send when answering a CQ),
the protocol exchanges must carry their details (RST/QTH/name,
rig/antenna/weather, age/years/key), the sign-off must include 73 and SK, and the
ending needs the two dits. If something is missing or you send a callsign that
belongs to neither station, the DX replies naming the missing items, for example
`W6ABC DE DL1ABC QTH? NAME? AGN`, and asks you to try again. After three tries it
accepts the over and continues so you never get stuck. Turn the checkbox off to
return to advisory-only reporting.

## How it works

| Module | Responsibility |
| --- | --- |
| `keyer/protocol.py` | WinKeyer host-mode command bytes, prosign encoding, buffer chunking |
| `keyer/device.py` | Device interface, events and the incoming byte decoder |
| `keyer/winkeyer.py` | Real serial backend (pyserial) with reader/writer/poll threads |
| `keyer/simulator.py` | Deterministic in-software WinKeyer for tests and hardware-free practice |
| `qso/script.py` | Builds the conversation turns from the CW QSO protocol |
| `qso/engine.py` | Walks the conversation and grades your overs |
| `gui/controller.py` | Bridges keyer events to the QSO engine using Qt signals |
| `gui/main_window.py` | The user interface |

The keyer interface opens the port, issues `Admin:Host Open`, switches to WK2
mode, enables paddle echo and autospace, and then streams ASCII to the device.
Incoming status bytes, speed-pot changes and character echoes are decoded on a
background thread and surfaced to the UI as events.

### Using a transmitter

The WinKeyer's key and PTT outputs can be connected to a real rig. The app sets
the PTT lead-in/tail delays and sidetone according to the configuration. If you
only want to practise, leave the key output disconnected and listen to the
WinKeyer's sidetone.

## Development

```sh
uv run ruff check --fix
uv run ruff format
uv run mypy .
uv run pytest
```

The test suite runs entirely against the simulated keyer, so it needs no
hardware.

## Acknowledgements

- QSO exchange structure based on the *CW QSO Protocol* reference sheet by W6JIM.
- WinKeyer protocol per the K1EL Winkeyer2 and WinKeyer3 IC datasheets.
