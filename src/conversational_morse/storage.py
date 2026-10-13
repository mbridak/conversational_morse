"""Loading and saving the application configuration as JSON."""

from __future__ import annotations

from pathlib import Path

from .config import AppConfig

APP_DIR_NAME = "conversational_morse"
CONFIG_FILE_NAME = "config.json"


def default_config_path() -> Path:
    """Return the per-user configuration file path."""
    return Path.home() / ".config" / APP_DIR_NAME / CONFIG_FILE_NAME


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from disk, falling back to defaults."""
    target = path or default_config_path()
    if not target.exists():
        return AppConfig.default()
    try:
        return AppConfig.model_validate_json(target.read_text(encoding="utf-8"))
    except ValueError:
        return AppConfig.default()


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    """Write configuration to disk, creating the parent directory."""
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return target
