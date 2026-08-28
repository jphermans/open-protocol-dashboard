"""KPI computations over the MaintenanceLog table.

Every function returns plain Python types (dicts, lists) so the Streamlit
layer can pipe them straight into st.metric / st.bar_chart / st.line_chart.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select, func

from app.db import session_scope
from app.models import MaintenanceLog


# ---------------------------------------------------------------------------
# Top-level counts
# ---------------------------------------------------------------------------
def total_rows() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count(MaintenanceLog.id))) or 0


def total_tightenings() -> int:
    """Sum of total_tightenings across all rows."""
    with session_scope() as s:
        return s.scalar(select(func.coalesce(
            func.sum(MaintenanceLog.total_tightenings), 0))) or 0


def ok_nok_counts() -> dict:
    """Distribution of tightening_status values."""
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.tightening_status,
                   func.count(MaintenanceLog.id))
            .where(MaintenanceLog.tightening_status.isnot(None))
            .group_by(MaintenanceLog.tightening_status)
        ).all()
    counts = Counter({(s_ or '(empty)'): c for s_, c in rows})
    return dict(counts)


def ok_rate() -> float:
    """Fraction of tightenings with status == 'OK', as a 0..1 float."""
    counts = ok_nok_counts()
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return counts.get('OK', 0) / total


# ---------------------------------------------------------------------------
# Time-bucketed trends
# ---------------------------------------------------------------------------
def trend_by_day(days: int = 30) -> list[dict]:
    """Daily count of new logs for the last `days` days."""
    with session_scope() as s:
        since = date.today() - timedelta(days=days - 1)
        rows = s.execute(
            select(MaintenanceLog.work_date,
                   func.count(MaintenanceLog.id))
            .where(MaintenanceLog.work_date >= since)
            .group_by(MaintenanceLog.work_date)
            .order_by(MaintenanceLog.work_date)
        ).all()
    # Backfill missing days so the chart has a continuous x-axis.
    by_day = {d: c for d, c in rows}
    out = []
    for i in range(days):
        d = since + timedelta(days=i)
        out.append({'day': d.isoformat(), 'count': by_day.get(d, 0)})
    return out


def trend_by_week(weeks: int = 12) -> list[dict]:
    """Weekly totals for the last `weeks` ISO weeks."""
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.work_date,
                   func.count(MaintenanceLog.id))
            .where(MaintenanceLog.work_date.isnot(None))
        ).all()
    by_week = Counter()
    for d, c in rows:
        iso = d.isocalendar()
        by_week[(iso.year, iso.week)] += c
    # Last N ISO weeks, backfilled.
    today = date.today()
    cursor = today
    keys: list[tuple[int, int]] = []
    for _ in range(weeks):
        iso = cursor.isocalendar()
        keys.append((iso.year, iso.week))
        cursor -= timedelta(days=7)
    keys.reverse()
    return [
        {'week': f'{y}-W{w:02d}', 'count': by_week.get((y, w), 0)}
        for (y, w) in keys
    ]


def trend_by_month(months: int = 12) -> list[dict]:
    """Monthly totals for the last `months` calendar months."""
    by_month = Counter()
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.work_date,
                   func.count(MaintenanceLog.id))
            .where(MaintenanceLog.work_date.isnot(None))
        ).all()
    for d, c in rows:
        by_month[(d.year, d.month)] += c
    today = date.today()
    cursor = today.replace(day=1)
    keys: list[tuple[int, int]] = []
    for _ in range(months):
        keys.append((cursor.year, cursor.month))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    keys.reverse()
    return [
        {'month': f'{y}-{m:02d}', 'count': by_month.get((y, m), 0)}
        for (y, m) in keys
    ]


# ---------------------------------------------------------------------------
# Distributions
# ---------------------------------------------------------------------------
def top_executors(n: int = 10) -> list[dict]:
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.executor,
                   func.count(MaintenanceLog.id))
            .where(MaintenanceLog.executor.isnot(None),
                   MaintenanceLog.executor != '')
            .group_by(MaintenanceLog.executor)
            .order_by(func.count(MaintenanceLog.id).desc())
            .limit(n)
        ).all()
    return [{'executor': e, 'count': c} for e, c in rows]


def top_tools(n: int = 10) -> list[dict]:
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.tool_serial,
                   func.count(MaintenanceLog.id))
            .where(MaintenanceLog.tool_serial.isnot(None),
                   MaintenanceLog.tool_serial != '')
            .group_by(MaintenanceLog.tool_serial)
            .order_by(func.count(MaintenanceLog.id).desc())
            .limit(n)
        ).all()
    return [{'tool_serial': t, 'count': c} for t, c in rows]


def top_sap_orders(n: int = 10) -> list[dict]:
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.sap_order,
                   func.count(MaintenanceLog.id))
            .where(MaintenanceLog.sap_order.isnot(None),
                   MaintenanceLog.sap_order != '')
            .group_by(MaintenanceLog.sap_order)
            .order_by(func.count(MaintenanceLog.id).desc())
            .limit(n)
        ).all()
    return [{'sap_order': o, 'count': c} for o, c in rows]


def status_distribution() -> list[dict]:
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.status,
                   func.count(MaintenanceLog.id))
            .where(MaintenanceLog.status.isnot(None),
                   MaintenanceLog.status != '')
            .group_by(MaintenanceLog.status)
            .order_by(func.count(MaintenanceLog.id).desc())
        ).all()
    return [{'status': st, 'count': c} for st, c in rows]


# ---------------------------------------------------------------------------
# Calibration alerts
# ---------------------------------------------------------------------------
def calibration_overdue(months: int = 12) -> list[dict]:
    """Tools whose last_calibration_date is older than `months` months ago."""
    cutoff = date.today() - timedelta(days=months * 30)
    with session_scope() as s:
        rows = s.execute(
            select(MaintenanceLog.tool_serial,
                   MaintenanceLog.last_calibration_date,
                   func.max(MaintenanceLog.work_date))
            .where(MaintenanceLog.tool_serial.isnot(None))
            .group_by(MaintenanceLog.tool_serial,
                      MaintenanceLog.last_calibration_date)
        ).all()
    out = []
    for tool, cal, last_seen in rows:
        # cal is a string like '20240815' (YYYYMMDD) — compare as date.
        cal_date = None
        if cal and cal.isdigit() and len(cal) == 8:
            try:
                cal_date = date(int(cal[:4]), int(cal[4:6]), int(cal[6:8]))
            except ValueError:
                cal_date = None
        if cal_date is None or cal_date < cutoff:
            out.append({
                'tool_serial'          : tool,
                'last_calibration_date': cal or '',
                'last_seen'            : last_seen.isoformat() if last_seen else '',
            })
    return out


# ---------------------------------------------------------------------------
# Aggregated stats
# ---------------------------------------------------------------------------
def avg_torque() -> float:
    with session_scope() as s:
        return s.scalar(select(func.avg(MaintenanceLog.torque_value))) or 0.0


def avg_angle() -> float:
    with session_scope() as s:
        return s.scalar(select(func.avg(MaintenanceLog.angle_value))) or 0.0


def last_seen_at() -> str:
    """ISO timestamp of the most recent log, or empty."""
    with session_scope() as s:
        v = s.scalar(select(func.max(MaintenanceLog.created_at)))
        return v.isoformat(timespec='seconds') if v else ''


# ---------------------------------------------------------------------------
# One-shot snapshot (cheaper to call once per render)
# ---------------------------------------------------------------------------
def snapshot() -> dict[str, Any]:
    counts = ok_nok_counts()
    return {
        'total_rows'        : total_rows(),
        'total_tightenings' : total_tightenings(),
        'ok_nok'            : counts,
        'ok_rate'           : ok_rate(),
        'avg_torque'        : avg_torque(),
        'avg_angle'         : avg_angle(),
        'last_seen_at'      : last_seen_at(),
        'top_executors'     : top_executors(),
        'top_tools'         : top_tools(),
        'top_sap_orders'    : top_sap_orders(),
        'status_dist'       : status_distribution(),
        'daily'             : trend_by_day(),
        'weekly'            : trend_by_week(),
        'monthly'           : trend_by_month(),
        'calibration_alerts': calibration_overdue(),
    }
