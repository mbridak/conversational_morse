# Changelog

All notable changes to this project are documented here.

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
- Full test suite, ruff and mypy clean.

### Fixed

- Paddle input is now captured as soon as the keyer is connected (and while the
  DX station is not transmitting), so characters keyed on the paddles appear in
  *Received from paddles* without first starting a QSO.
- Echoes are no longer discarded when the WinKeyer's `break-in` bit has already
  dropped; since serial echo is disabled, every echo is operator paddle input.
