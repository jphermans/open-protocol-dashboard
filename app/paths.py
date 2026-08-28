"""Path resolution and platform helpers.

Used by both the launcher (run.py) and the running app (streamlit_app.py)
to figure out:

  * BASE_DIR — the project root (next to run.py / app/)
  * DB_PATH  — local SQLite file when DATABASE_URL is unset
  * platform — 'windows' / 'wsl' / 'linux' / 'macos' / 'unknown'

The platform string is exposed via `app.paths.PLATFORM` so the UI can show
the operator what the launcher decided.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def _detect_platform() -> str:
    s = sys.platform
    if s.startswith("win"):
        return "windows"
    if s == "linux":
        try:
            with open("/proc/version", "r", encoding="utf-8") as f:
                txt = f.read().lower()
            if "microsoft" in txt or "wsl" in txt:
                return "wsl"
        except OSError:
            pass
        return "linux"
    if s == "darwin":
        return "macos"
    return "unknown"


PLATFORM = os.environ.get("OPEN_PROTOCOL_PLATFORM", _detect_platform())


def _default_sqlite_url() -> str:
    """Default DB URL when DATABASE_URL is not set: SQLite file in BASE_DIR."""
    db_file = PROJECT_DIR / "database.sqlite"
    return f"sqlite:///{db_file.as_posix()}"


def get_database_url() -> str:
    """Return the active DATABASE_URL (env var wins, else default SQLite)."""
    return os.environ.get("DATABASE_URL", _default_sqlite_url())


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")
