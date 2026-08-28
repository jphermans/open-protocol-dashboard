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

# Bundled static assets (logo, icons). These travel with the repo and
# inside PyInstaller builds (see build_windows.bat --add-data flag).
ASSETS_DIR = PROJECT_DIR / "assets"
LOGO_FILE = ASSETS_DIR / "atlas_copco_logo.png"


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
    """Resolve the active DATABASE_URL by precedence:

    1. ``DATABASE_URL`` environment variable (highest priority — keeps
       the existing ``.env`` / ``run.py --db ...`` behaviour).
    2. ``db_config.json`` on disk (saved by the Setup tab in the UI).
    3. Default SQLite file in the project folder.
    """
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    try:
        # Lazy import to avoid a circular dep at module load.
        from app.config import load_db_config, build_database_url
        cfg = load_db_config()
        if cfg:
            url = build_database_url(cfg)
            if url:
                return url
    except Exception:
        # Any failure (config missing, malformed, driver not installed)
        # falls through to the SQLite default rather than crashing the app.
        pass
    return _default_sqlite_url()


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")
