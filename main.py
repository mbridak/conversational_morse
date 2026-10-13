"""Convenience entry point so the app can run with ``uv run python main.py``."""

from __future__ import annotations

from conversational_morse.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
