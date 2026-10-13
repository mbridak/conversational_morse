"""Application entry point."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from .gui import MainWindow
from .storage import load_config


def main() -> int:
    """Launch the Conversational Morse application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Conversational Morse")

    window = MainWindow(load_config())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
