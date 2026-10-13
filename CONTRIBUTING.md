# Contributing

Thanks for your interest in Conversational Morse. This project uses modern
Python tooling and a strict quality bar; please keep changes consistent with the
existing layout and style.

## Setup

```sh
uv sync
```

Always run commands through `uv run` rather than a global interpreter.

## Quality gates

Run all of these before opening a pull request and fix anything you introduce:

```sh
uv run ruff check --fix
uv run ruff format
uv run mypy .
uv run pytest
```

## Guidelines

- Python 3.12+, `from __future__ import annotations` at the top of every module.
- Add explicit PEP 484 type hints to all new functions and classes.
- Use `pathlib.Path` instead of `os.path`.
- Use `pydantic` models for configuration and parsing.
- `snake_case` for functions and variables, `PascalCase` for classes,
  `UPPER_CASE` for constants, and an 88 character line limit.
- Prefer the `KeyerDevice` interface so new behaviour works with both the real
  WinKeyer backend and the simulator.
- Add tests under `tests/`. The suite must run without hardware.

## Layout

- `src/conversational_morse/keyer/` - WinKeyer protocol, serial backend and
  simulator.
- `src/conversational_morse/qso/` - conversation scripts, models and engine.
- `src/conversational_morse/gui/` - the PyQt6 interface and Qt controller.

## Releasing

The package version is read by hatchling from `src/conversational_morse/__init__.py`,
so there is a single place to bump it.

1. Update `__version__` in `src/conversational_morse/__init__.py` and add a
   matching entry to `CHANGELOG.md`.
2. Build the distributions and validate the metadata:

   ```sh
   rm -rf dist
   uv build
   uv run --with twine twine check dist/*
   ```

3. Upload to PyPI. Test the process against TestPyPI first if you like:

   ```sh
   uv publish --index testpypi
   uv publish
   ```

   `uv publish` takes the API token from the `UV_PUBLISH_TOKEN` environment
   variable, `~/.pypirc`, or the system keyring, and prompts when none is set.

