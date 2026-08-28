"""CRUD operations on MaintenanceLog.

All functions take a `Session` (or `None` to open their own), operate
inside `session_scope()` for atomicity, and return Python dataclass-like
dicts (via MaintenanceLog.as_display_dict) so the Streamlit layer never
touches ORM objects directly.

Natural-key uniqueness is enforced at the DB layer:
    (sap_order, work_date, tool_serial, tightening_id).

`create_log_from_controller()` uses `INSERT ... ON CONFLICT DO NOTHING`
when the backend is PostgreSQL, falling back to a manual check on SQLite
and MySQL, so re-fetching identical data does not raise.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional

from sqlalchemy import select, func, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import session_scope
from app.models import MaintenanceLog


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def list_logs(limit: int = 500, offset: int = 0,
              order_desc: bool = True) -> list[dict]:
    """Return most recent rows (default: 500 newest first)."""
    with session_scope() as s:
        q = select(MaintenanceLog)
        q = q.order_by(MaintenanceLog.id.desc() if order_desc
                       else MaintenanceLog.id.asc())
        q = q.limit(limit).offset(offset)
        return [r.as_display_dict() for r in s.execute(q).scalars()]


def get_log(log_id: int) -> Optional[dict]:
    with session_scope() as s:
        row = s.get(MaintenanceLog, log_id)
        return row.as_display_dict() if row else None


def get_log_by_offset(offset: int, order_desc: bool = True) -> Optional[dict]:
    """Return the row at position `offset` in the id-sorted list.

    `offset` is 0-indexed. With `order_desc=True` (default) the newest row
    is at offset 0 and the oldest at offset (count-1). Robust against
    id gaps caused by deletes — positions are derived from ORDER BY + LIMIT,
    not from id arithmetic.
    """
    with session_scope() as s:
        q = (select(MaintenanceLog)
             .order_by(MaintenanceLog.id.desc() if order_desc
                       else MaintenanceLog.id.asc())
             .limit(1)
             .offset(max(0, offset)))
        row = s.execute(q).scalar_one_or_none()
        return row.as_display_dict() if row else None


def get_prev_log(current_id: int, order_desc: bool = True) -> Optional[dict]:
    """Return the row whose id is the nearest neighbour smaller than `current_id`.

    With `order_desc=True` (default, matches list_logs) this returns the
    chronologically newer row when called from the Browse tab's
    'Previous' button.
    """
    with session_scope() as s:
        if order_desc:
            q = (select(MaintenanceLog)
                 .where(MaintenanceLog.id > current_id)
                 .order_by(MaintenanceLog.id.asc())
                 .limit(1))
        else:
            q = (select(MaintenanceLog)
                 .where(MaintenanceLog.id < current_id)
                 .order_by(MaintenanceLog.id.desc())
                 .limit(1))
        row = s.execute(q).scalar_one_or_none()
        return row.as_display_dict() if row else None


def get_next_log(current_id: int, order_desc: bool = True) -> Optional[dict]:
    """Inverse of `get_prev_log`."""
    with session_scope() as s:
        if order_desc:
            q = (select(MaintenanceLog)
                 .where(MaintenanceLog.id < current_id)
                 .order_by(MaintenanceLog.id.desc())
                 .limit(1))
        else:
            q = (select(MaintenanceLog)
                 .where(MaintenanceLog.id > current_id)
                 .order_by(MaintenanceLog.id.asc())
                 .limit(1))
        row = s.execute(q).scalar_one_or_none()
        return row.as_display_dict() if row else None


def get_first_log(order_desc: bool = True) -> Optional[dict]:
    """Return the newest (or oldest, if `order_desc=False`) row."""
    with session_scope() as s:
        q = (select(MaintenanceLog)
             .order_by(MaintenanceLog.id.desc() if order_desc
                       else MaintenanceLog.id.asc())
             .limit(1))
        row = s.execute(q).scalar_one_or_none()
        return row.as_display_dict() if row else None


def get_last_log(order_desc: bool = True) -> Optional[dict]:
    """Return the oldest (or newest, if `order_desc=False`) row."""
    return get_first_log(order_desc=not order_desc)


def search_logs(
    *,
    executor: str = '',
    status: str = '',
    sap_order: str = '',
    tool_serial: str = '',
    work_date_from: Optional[date] = None,
    work_date_to: Optional[date] = None,
    tightening_status: str = '',
    limit: int = 500,
) -> list[dict]:
    """Filter logs by any combination of fields. All filters are AND-ed."""
    with session_scope() as s:
        q = select(MaintenanceLog)
        if executor.strip():
            q = q.where(MaintenanceLog.executor.like(f'%{executor.strip()}%'))
        if status.strip():
            q = q.where(MaintenanceLog.status.like(f'%{status.strip()}%'))
        if sap_order.strip():
            q = q.where(MaintenanceLog.sap_order.like(f'%{sap_order.strip()}%'))
        if tool_serial.strip():
            q = q.where(MaintenanceLog.tool_serial.like(f'%{tool_serial.strip()}%'))
        if work_date_from:
            q = q.where(MaintenanceLog.work_date >= work_date_from)
        if work_date_to:
            q = q.where(MaintenanceLog.work_date <= work_date_to)
        if tightening_status.strip():
            q = q.where(MaintenanceLog.tightening_status == tightening_status.strip())
        q = q.order_by(MaintenanceLog.id.desc()).limit(limit)
        return [r.as_display_dict() for r in s.execute(q).scalars()]


def count_logs() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count(MaintenanceLog.id))) or 0


def executors() -> list[str]:
    """Distinct non-empty executor names, useful for autocomplete."""
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.executor)
            .where(MaintenanceLog.executor.isnot(None),
                   MaintenanceLog.executor != '')
            .distinct().order_by(MaintenanceLog.executor)
        ).all()
        return [r[0] for r in rows]


def sap_orders() -> list[str]:
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.sap_order)
            .where(MaintenanceLog.sap_order.isnot(None),
                   MaintenanceLog.sap_order != '')
            .distinct().order_by(MaintenanceLog.sap_order)
        ).all()
        return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def create_log(data: dict) -> tuple[dict, str]:
    """Insert one log row.

    Returns (display_dict, status) where status is 'CREATED' or 'DUPLICATE'.
    On duplicate, the existing row is returned unchanged.
    """
    # Reject blank records at the server side too, so any caller
    # that bypasses the Streamlit UI gate cannot insert empties.
    _required = ("tool_serial", "tool_type", "work_date", "executor")
    _missing = [
        k for k in _required
        if data.get(k) is None
        or (isinstance(data.get(k), str) and not data.get(k).strip())
    ]
    if _missing:
        return ({"missing": _missing}, "MISSING")

    with session_scope() as s:
        # Try PostgreSQL ON CONFLICT first (atomic), then fall back.
        try:
            stmt = pg_insert(MaintenanceLog).values(**_normalise(data))
            stmt = stmt.on_conflict_do_nothing(
                index_elements=['sap_order', 'work_date',
                                'tool_serial', 'tightening_id'])
            res = s.execute(stmt)
            if res.rowcount == 0:
                return _reload(s, data), 'DUPLICATE'
            s.commit()
            return _reload(s, data), 'CREATED'
        except Exception:
            s.rollback()

        # Fallback: manual dedup via SELECT then INSERT.
        existing = _find_existing(s, data)
        if existing is not None:
            return existing.as_display_dict(), 'DUPLICATE'
        try:
            row = MaintenanceLog(**_normalise(data))
            s.add(row)
            s.commit()
            return row.as_display_dict(), 'CREATED'
        except IntegrityError:
            s.rollback()
            existing = _find_existing(s, data)
            return existing.as_display_dict(), 'DUPLICATE'


def create_log_from_controller(controller_data: dict) -> tuple[dict, str]:
    """Insert a row from a controller pull.

    `controller_data` is expected to have all the Open Protocol fields plus
    the XLSX-style fields it can derive (work_date=today, source='controller').
    """
    return create_log({'source': 'controller', **controller_data})


def update_log(log_id: int, data: dict) -> Optional[dict]:
    """Update an existing log row. Returns the new dict, or None if not found."""
    with session_scope() as s:
        row = s.get(MaintenanceLog, log_id)
        if row is None:
            return None
        for k, v in _normalise(data).items():
            if hasattr(row, k):
                setattr(row, k, v)
        s.commit()
        return row.as_display_dict()


def delete_log(log_id: int) -> bool:
    with session_scope() as s:
        res = s.execute(delete(MaintenanceLog).where(MaintenanceLog.id == log_id))
        return (res.rowcount or 0) > 0


def bulk_create(rows: Iterable[dict]) -> dict:
    """Insert many rows. Returns {'created': N, 'duplicate': M}."""
    created = duplicate = 0
    for row in rows:
        _, status = create_log(row)
        if status == 'CREATED':
            created += 1
        else:
            duplicate += 1
    return {'created': created, 'duplicate': duplicate}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalise(data: dict) -> dict:
    """Coerce types so SQLAlchemy accepts the payload from Streamlit inputs."""
    out = {}
    for k, v in data.items():
        if v == '' or v is None:
            out[k] = None
            continue
        if k == 'work_date' and isinstance(v, str):
            try:
                out[k] = datetime.strptime(v, '%Y-%m-%d').date()
            except ValueError:
                out[k] = None
            continue
        if k in {'total_tightenings', 'tightenings_since_svc',
                 'batch_counter', 'controller_port'}:
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                out[k] = None
            continue
        if k in {'torque_value', 'torque_min', 'torque_target', 'torque_max',
                 'angle_value', 'angle_min', 'angle_target', 'angle_max'}:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                out[k] = None
            continue
        out[k] = v
    return out


def _find_existing(s: Session, data: dict) -> Optional[MaintenanceLog]:
    sap = data.get('sap_order')
    wd  = data.get('work_date')
    ts  = data.get('tool_serial')
    tid = data.get('tightening_id')
    return s.execute(
        select(MaintenanceLog)
        .where(MaintenanceLog.sap_order == sap,
               MaintenanceLog.work_date == wd,
               MaintenanceLog.tool_serial == ts,
               MaintenanceLog.tightening_id == tid)
    ).scalar_one_or_none()


def _reload(s: Session, data: dict) -> dict:
    row = _find_existing(s, data)
    return row.as_display_dict() if row else {}
