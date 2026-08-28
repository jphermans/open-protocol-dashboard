"""Database engine + session factory.

Resolves `DATABASE_URL` by precedence (env var > db_config.json >
default SQLite), so the Setup tab can switch databases at runtime.

Supports any URL SQLAlchemy accepts:
  * sqlite:///path/to/file.db
  * postgresql://user:pw@host:5432/db
  * mysql+pymysql://user:pw@host:3306/db
  * mssql+pyodbc://...
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.paths import get_database_url, is_sqlite

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def reset_engine() -> None:
    """Drop the cached engine + session factory so the next call to
    ``get_engine()`` re-resolves ``get_database_url()`` and creates a
    fresh engine. Called by the Setup tab after the user saves a new
    configuration.
    """
    global _engine, _SessionLocal
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _SessionLocal = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_database_url()
        connect_args = {"check_same_thread": False} if is_sqlite(url) else {}
        _engine = create_engine(
            url,
            future=True,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


def init_db() -> None:
    """Create tables if they do not exist. Idempotent."""
    Base.metadata.create_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager that commits on success, rolls back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
