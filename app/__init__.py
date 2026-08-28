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

Lazy public re-exports:
    `from app import version_string` and `from app import __version__` are
    side-effect-free — they do NOT trigger imports of sqlalchemy /
    streamlit / pandas. The DB / paths submodules are imported on first
    attribute access (PEP 562 module __getattr__). This lets `run.py
    --version` work even when sqlalchemy is not installed in the
    Python that is currently on PATH (e.g. system Python instead of
    the project venv).
"""
from __future__ import annotations

import importlib

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "1.1.2"
__version_info__ = tuple(int(x) for x in __version__.split("."))


def version_string() -> str:
    """Plain-text version suitable for CLI banners and HTTP headers."""
    return f"Open Protocol CRUD Dashboard v{__version__}"


# ---------------------------------------------------------------------------
# Lazy public re-exports
# ---------------------------------------------------------------------------
_LAZY_ATTRS: dict[str, str] = {
    "init_db":          "app.db",
    "session_scope":    "app.db",
    "PROJECT_DIR":      "app.paths",
    "PLATFORM":         "app.paths",
    "get_database_url": "app.paths",
    "is_sqlite":        "app.paths",
}


def __getattr__(name: str):  # PEP 562 — called only when attribute is missing
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module 'app' has no attribute {name!r}")
    submodule = importlib.import_module(target)
    value = getattr(submodule, name)
    globals()[name] = value  # cache so subsequent lookups skip the indirection
    return value


__all__ = [
    "__version__",
    "__version_info__",
    "version_string",
    "init_db",
    "session_scope",
    "PROJECT_DIR",
    "PLATFORM",
    "get_database_url",
    "is_sqlite",
]
