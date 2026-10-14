# Changelog

All notable changes to this project are documented here.

## 0.2.0

### Added

- Sidetone volume control (normal or low), applied when you connect and whenever
  you change the setting. It needs WinKeyer firmware revision 31 or later.
- A **Show DX output** option to hide what the simulated station sends, so you
  can practise copying by ear.
- Operator-initiated repeat requests. Send a partial callsign plus a question
  mark (`W6?`) to hear the DX callsign twice when answering a CQ, or name a
  detail (`RST?`, `QTH?`, `NAME?`, `RIG?`, `ANT?`, `WX?`, `AGE?`, `YRS?`,
  `KEY?`) later in the contact to have the DX resend it; the over then resumes.

## 0.1.0

### Added

- PyQt6 desktop application for practising realistic CW QSOs.
- K1EL WinKeyer USB backend (host mode) for transmitting Morse and reading
  paddle echo.
- Simulated WinKeyer backend for hardware-free practice and deterministic tests.
- Simulated contacts that follow the W6JIM CW QSO protocol: call CQ or answer a
  CQ, run the RST/QTH/name, rig/antenna/weather and age/years/key exchanges, and
  sign off with 73/SK and the two closing dits.
- Copy grading that checks whether your overs contained the expected
  information, with three contact lengths (short, medium, full).
- Station setup dialog and JSON configuration persistence.
- Packaged for distribution on PyPI: full project metadata, an MIT license, a
  `conversational-morse` console entry point, a `py.typed` marker, and a version
  single-sourced from the package.
- Full test suite, ruff and mypy clean.

### Changed

- The DX station now checks every operator over before continuing. Missing
  information or a callsign that matches neither station makes the DX ask for a
  repeat, naming the items to resend. After three tries it moves on. The checks
  cover each portion, including your own callsign in the CQ answer, all protocol
  details, the 73/SK sign-off and the closing two dits. Answering a CQ now sends
  just your own callsign (as it should), and naming the DX station is not
  treated as an error.
- Added a **Require correct copy** setting (on by default) to return to
  advisory-only reporting.

### Fixed

- Paddle input is now captured as soon as the keyer is connected (and while the
  DX station is not transmitting), so characters keyed on the paddles appear in
  *Received from paddles* without first starting a QSO.
- Echoes are no longer discarded when the WinKeyer's `break-in` bit has already
  dropped; since serial echo is disabled, every echo is operator paddle input.
