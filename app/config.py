"""Runtime DB configuration: mode + connection fields, persisted in
`<project>/db_config.json`. Created/edited via the Setup tab in the UI.

Resolution order used by `app.paths.get_database_url()`:

    1. `DATABASE_URL` environment variable (highest priority — keeps
       existing `.env` / `run.py --db ...` behaviour).
    2. `db_config.json` on disk (whatever the Setup tab last saved).
    3. Built-in default: local SQLite in the project folder.

File format (all keys optional; missing keys fall back to defaults):

    {
      "mode":         "local" | "remote",
      "driver":       "postgresql" | "mysql+pymysql" | "mssql+pyodbc",
      "host":         "db.example.com",
      "port":         5432,
      "login":        "op_dashboard",
      "password":     "<secret>",
      "database":     "open_protocol",
      "sqlite_path":  "./database.sqlite"
    }
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from app.paths import PROJECT_DIR


# The config file location can be overridden via env var (useful for tests
# and PyInstaller single-file builds where you want the config next to the
# exe rather than inside a temporary extracted folder).
CONFIG_FILE = Path(
    os.environ.get(
        "OPEN_PROTOCOL_CONFIG_FILE",
        str(PROJECT_DIR / "db_config.json"),
    )
)


DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "local",
    "sqlite_path": "./database.sqlite",
}

DEFAULT_REMOTE_PORTS: dict[str, int] = {
    "postgresql": 5432,
    "mysql+pymysql": 3306,
    "mssql+pyodbc": 1433,
}

# Human-readable labels for each SQLAlchemy dialect + driver. Used by the
# Setup tab selectbox so users see "PostgreSQL (psycopg2-binary)" instead
# of the raw "postgresql" URL prefix. Unknown drivers fall back to their
# raw value via `DRIVER_LABELS.get(d, d)`.
DRIVER_LABELS: dict[str, str] = {
    "postgresql":    "PostgreSQL (psycopg2-binary / psycopg)",
    "mysql+pymysql": "MySQL / MariaDB (pymysql)",
    "mssql+pyodbc":  "Microsoft SQL Server (pyodbc + ODBC Driver)",
}

# Reference panel shown in the Setup tab expander. Documents every DB
# system the dashboard can talk to, not just the 3 currently in the
# selectbox — so users know the door is wider than the visible list.
#
#   key               : SQLAlchemy dialect + driver string
#   display_name      : what to show users
#   default_port      : canonical TCP port (or None for file-based)
#   example_url       : realistic placeholder URL with redaction markers
#   pip_install       : exact pip install command for the driver
#   notes             : extra info (ODBC requirement, SSL, etc.)
SUPPORTED_DATABASES: list[dict[str, object]] = [
    {
        "key"          : "sqlite",
        "display_name" : "SQLite (file-based, no driver needed)",
        "default_port" : None,
        "example_url"  : "sqlite:////var/lib/open-protocol/database.sqlite",
        "pip_install"  : "— (built into Python)",
        "notes"        : "Single file. No auth, no network, no extra deps.",
    },
    {
        "key"          : "postgresql",
        "display_name" : "PostgreSQL",
        "default_port" : 5432,
        "example_url"  : "postgresql://op_dashboard:***@db.example.com:5432/open_protocol",
        "pip_install"  : "pip install 'psycopg2-binary'   # or  pip install psycopg",
        "notes"        : "Default driver. For production use 'psycopg' (v3) without 'binary'.",
    },
    {
        "key"          : "mysql+pymysql",
        "display_name" : "MySQL / MariaDB",
        "default_port" : 3306,
        "example_url"  : "mysql+pymysql://op_dashboard:***@db.example.com:3306/open_protocol",
        "pip_install"  : "pip install pymysql",
        "notes"        : "Pure-Python driver, works with both MySQL and MariaDB.",
    },
    {
        "key"          : "mssql+pyodbc",
        "display_name" : "Microsoft SQL Server (MSSQL)",
        "default_port" : 1433,
        "example_url"  : "mssql+pyodbc://op_dashboard:***@db.example.com:1433/open_protocol?driver=ODBC+Driver+17+for+SQL+Server",
        "pip_install"  : "pip install pyodbc    # also install 'ODBC Driver 17/18 for SQL Server' from Microsoft",
        "notes"        : "Requires an OS-level ODBC driver. On Linux: 'msodbcsql17' Debian package.",
    },
    {
        "key"          : "oracle+oracledb",
        "display_name" : "Oracle Database",
        "default_port" : 1521,
        "example_url"  : "oracle+oracledb://op_dashboard:***@db.example.com:1521/?service_name=OPENPROT",
        "pip_install"  : "pip install oracledb    # successor to the deprecated cx_Oracle",
        "notes"        : "Use 'service_name' or 'sid' query string; no driver in the selectbox yet (edit db_config.json manually).",
    },
    {
        "key"          : "snowflake",
        "display_name" : "Snowflake (cloud DW)",
        "default_port" : 443,
        "example_url"  : "snowflake://op_dashboard:***@acme.eu-west-1.snowflakecomputing.com/open_protocol?warehouse=COMPUTE_WH",
        "pip_install"  : "pip install snowflake-sqlalchemy",
        "notes"        : "Use the Snowflake account locator, not the full URL hostname.",
    },
    {
        "key"          : "duckdb",
        "display_name" : "DuckDB (analytical, file-based)",
        "default_port" : None,
        "example_url"  : "duckdb:///var/lib/open-protocol/analytics.duckdb",
        "pip_install"  : "pip install duckdb-engine duckdb",
        "notes"        : "OLAP-style queries. Useful for the KPI tab on very large logs.",
    },
]


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def load_db_config() -> dict[str, Any]:
    """Return the on-disk config merged with DEFAULT_CONFIG. Never raises."""
    try:
        on_disk = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(DEFAULT_CONFIG)
    except (json.JSONDecodeError, OSError):
        # Corrupt / unreadable — fall back to defaults rather than blowing up
        # the Streamlit page.
        return dict(DEFAULT_CONFIG)
    merged = {**DEFAULT_CONFIG, **on_disk}
    return merged


def save_db_config(cfg: dict[str, Any]) -> None:
    """Persist the config atomically (write-to-temp-then-replace)."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(cfg, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(tmp, CONFIG_FILE)


# ---------------------------------------------------------------------------
# Build URL
# ---------------------------------------------------------------------------
def build_database_url(cfg: dict[str, Any]) -> str:
    """Turn the config dict into a SQLAlchemy URL string."""
    mode = (cfg.get("mode") or "local").lower()
    if mode == "local":
        path = cfg.get("sqlite_path") or "./database.sqlite"
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_DIR / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{p.as_posix()}"
    if mode == "remote":
        driver = cfg.get("driver") or "postgresql"
        host   = (cfg.get("host") or "localhost").strip()
        port   = int(cfg.get("port") or DEFAULT_REMOTE_PORTS.get(driver, 5432))
        login  = cfg.get("login") or ""
        pwd    = cfg.get("password") or ""
        db     = (cfg.get("database") or "").strip()
        if not host:
            raise ValueError("Remote DB: 'host' is required.")
        if not db:
            raise ValueError("Remote DB: 'database' name is required.")
        auth = ""
        if login:
            auth = f"{quote_plus(login)}:{quote_plus(pwd)}@"
        return f"{driver}://{auth}{host}:{port}/{db}"
    raise ValueError(f"Unknown DB mode: {mode!r}")


def redact_password(url: str) -> str:
    """Hide the password segment of a SQLAlchemy URL for safe display."""
    return re.sub(r":[^:/@]+@", ":***@", url)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------
def test_connection(cfg: dict[str, Any], timeout_s: int = 5) -> tuple[bool, str]:
    """Try to connect with the given config. Returns (ok, message)."""
    try:
        url = build_database_url(cfg)
    except ValueError as exc:
        return False, f"Invalid config: {exc}"
    try:
        from sqlalchemy import create_engine
        if url.startswith("sqlite"):
            # SQLite: just check we can connect — no auth, no network.
            eng = create_engine(url, future=True)
            with eng.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            eng.dispose()
            return True, f"OK — connected to {redact_password(url)}"
        # Remote: short connect timeout so the UI doesn't hang.
        eng = create_engine(
            url,
            future=True,
            connect_args={"connect_timeout": timeout_s} if "postgresql" in url or "mysql" in url else {},
        )
        with eng.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        eng.dispose()
        return True, f"OK — connected to {redact_password(url)}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
