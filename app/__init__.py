"""Open Protocol CRUD dashboard — app package.

Versioning follows Semantic Versioning 2.0 (https://semver.org):
    MAJOR.MINOR.PATCH

  * MAJOR — incompatible schema or UI rewrite.
  * MINOR — new feature, backward-compatible (e.g. new MIDs, new KPI).
  * PATCH — bug fix, copy/wording change, dependency bump.

This constant is the single source of truth: it is read by:

  * run.py (printed at startup and on --version)
  * app/streamlit_app.py (shown in the sidebar)
  * the README and CHANGELOG

When bumping, also:
  1. Update CHANGELOG.md with the new entry on top.
  2. Commit `app/__init__.py` and `CHANGELOG.md` together.
  3. Tag the commit with `git tag v<__version__>`.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "1.0.0"
__version_info__ = tuple(int(x) for x in __version__.split("."))

# ---------------------------------------------------------------------------
# Public re-exports (so callers can `from app import init_db, snapshot`)
# ---------------------------------------------------------------------------
from app.db import init_db, session_scope              # noqa: E402,F401
from app.paths import (
    PROJECT_DIR, PLATFORM, get_database_url, is_sqlite  # noqa: E402,F401
)


def version_string() -> str:
    """Plain-text version suitable for CLI banners and HTTP headers."""
    return f"Open Protocol CRUD Dashboard v{__version__}"


__all__ = [
    '__version__',
    '__version_info__',
    'init_db',
    'session_scope',
    'PROJECT_DIR',
    'PLATFORM',
    'get_database_url',
    'is_sqlite',
    'version_string',
]
