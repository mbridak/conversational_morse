# AGENTS.md - Guide for AI-Assisted Development

You are an expert Python software engineer joining our development team. Follow these instructions strictly for all tasks, file edits, and tool usage within this repository.

## 🛠️ Environment & Setup
Our project relies on modern Python package management. Do NOT use standard `pip` or global environments.

- **Python Version:** 3.12+ (Prefer 3.13 features where applicable)
- **Package & Env Manager:** `uv`
- **Installation Command:** `uv sync`
- **Environment Execution:** Always prefix execution commands with `uv run` (e.g., `uv run python main.py`)
- **GUI:** Use PyQt6

## 🚀 Quality Gates & Verification Commands
Before completing a task or marking it as resolved, you MUST run these exact validation steps and fix any failures you introduce.

- **Linting & Formatting:** `uv run ruff check --fix` and `uv run ruff format`
- **Type Checking:** `uv run mypy .`
- **Testing:** `uv run pytest`
  - *Rule:* Never drop or suppress failing tests. Fix the underlying code bug or adjust the test file if the spec legitimately changed.

## 🐍 Coding Conventions & Style
Follow these idiomatic Python constraints to maintain architectural consistency:

- **Type Hints:** All new function signatures and class definitions MUST include explicit, strict PEP 484 type hints. Use `from typing import ...` for complex types.
- **Path Manipulation:** Always use the object-oriented `pathlib.Path` standard. NEVER use `os.path` operations.
- **Validation:** Use `pydantic` models for configuration, data parsing, and API request/response validation. 
- **Naming Conventions:** 
  - `snake_case` for functions, variables, and modules.
  - `PascalCase` for classes.
  - `UPPER_CASE` for global or class-level constants.
- **Line Length:** Code lines must be limited to 88 characters (conforming to our Ruff formatter settings).
- **Comments:** Avoid redundant, self-demonstrating comments (e.g., `# Increment x by 1`). Only comment on complex underlying algorithms or unexpected edge cases. Do not use emojis in comments or commit messages.

## 🛑 Guardrails & Boundaries

### ALWAYS DO
- Write descriptive, meaningful variable and function names.
- Ensure new features have complete test coverage in the `tests/` directory.
- Use explicit `print()` blocks when displaying DataFrames inside Jupyter Notebooks (they do not auto-render in this agent environment).

### ASK FIRST
- Ask for user confirmation before modifying database schemas or running migrations.
- Ask before adding or upgrading third-party dependencies in `pyproject.toml`.

### NEVER DO
- NEVER use standard `string`/`text` types for timestamps or JSON columns in data schemas; always use appropriate `DATETIME` or structured primitives.
- NEVER leave `TODO` or placeholder comments in finalized PR code submissions.
- NEVER touch or modify any credentials or files inside the `.env.example` file without permission.
