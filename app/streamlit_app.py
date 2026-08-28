"""Tool CRUD Dashboard — Streamlit entry point.

Run with:
    streamlit run app/streamlit_app.py
or (preferred):
    python run.py

Layout:
  * Title + version banner
  * Sidebar: live DB stats + platform info + auth widget + refresh button
  * Tab 1 - Live: controller pull (MID 0040 / 0060 / 0080 / 0010 / 0030)
  * Tab 2 - CRUD: create / read / browse / update / delete maintenance log rows
  * Tab 3 - KPIs: snapshot metrics + charts
  * Tab 4 - Search: filter the log table and export CSV
  * Tab 5 - Setup: local SQLite vs remote DB configuration

Product name: "Tool CRUD Dashboard" (renamed in v1.2.1). The dashboard
talks to controllers over Atlas Copco Open Protocol; "Open Protocol"
in the rest of this file refers to that wire protocol, not the
product name.
"""
from __future__ import annotations

import socket
import time
from datetime import date, datetime

import pandas as pd
import streamlit as st

from app import (
    __version__,
    PLATFORM,
    PROJECT_DIR,
    get_database_url,
    init_db,
    is_sqlite,
    version_string,
)
from app.paths import LOGO_FILE
import app.auth as auth
import app.crud as crud
import app.kpis as kpis
import app.protocol as protocol


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
# Emoji icons used in section headers and labels across the dashboard.
# Centralised here so a single change updates every appearance (and so
# missing-reference errors like the NameError we shipped in v1.2.4--v1.2.6
# become impossible: any icon must be defined in this block).
WRENCH = '\U0001F527'   # 🔧  - the product icon, used in titles, Setup-tab
                       #        section headers, and the destructive-action
                       #        password panel.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Field tooltips (hover-text on every form input)\# ---------------------------------------------------------------------------
# Tooltip text is derived from the 'TMC Herstellingen ASML' XLSX schema:
# executor, status, SAP order, SAP status options, work date, start time,
# end time. Open Protocol fields (tool serial, controller serial, firmware,
# total tightenings, ...) are described from the Atlas Copco Open Protocol
# MID 0040 / 0060 / 0080 spec.
#
# Pass help=_HELP.get('key', '') to every st.text_input / st.number_input /
# st.selectbox / st.date_input / st.text_area call. Streamlit renders an
# info-icon next to the label; the hover text matches the entry below.
_HELP: dict[str, str] = {
    # CREATE / UPDATE form
    'executor':
        "Person who performed the maintenance (XLSX column 'UITVOERDER'). "
        "Free text, e.g. 'Sandro Mura' or 'Last First'. Required for audit trail.",
    'sap_order':
        "SAP work-order number (XLSX column 'ORDER SAP'). Alphanumeric code "
        "such as 'FSTDEC8556'. Use '0000000000' if no SAP order applies.",
    'sap_status_options':
        "SAP system status flag (XLSX column 'STATUS OPTIES SAP'). "
        "Often blank. Use whatever status string your SAP instance carries, "
        "e.g. 'Released', 'In process', 'TECO'.",
    'status':
        "Current work-order status (XLSX column 'AFWERING STATUS'). "
        "'Finished' = closed and signed off, "
        "'In progress' = still being worked on, "
        "'Cancelled' = no longer needed, "
        "'Waiting for parts' = blocked on inventory.",
    'work_date':
        "Date the maintenance was performed (XLSX column 'DATUM'). Default: today. "
        "Stored as ISO 8601 (YYYY-MM-DD); the XLSX sample uses M/D/YYYY (e.g. 9/8/2025).",
    'start_time':
        "When the work started (XLSX column 'BEGIN'). Free text HH:MM or HH:MM:SS "
        "(e.g. '08:15' or '08:15:30'). Leave blank if not recorded.",
    'end_time':
        "When the work finished (XLSX column 'EIND'). Free text HH:MM or HH:MM:SS. "
        "Leave blank if not recorded.",
    'tool_serial':
        "Atlas Copco / Power-Focus / Power-TEC tool serial number "
        "(e.g. 'A4411212'). Auto-filled when this row was created by an "
        "Open Protocol pull (MID 0040); leave blank for manual-only entries.",
    'tool_type':
        "Tool model / type identifier (e.g. ETX, Tensor, QST). Auto-populated "
        "from Open Protocol MID 0040 (bytes 36-56, revision-dependent). Required "
        "for creating a maintenance record; click Fetch from controller below "
        "to populate automatically.",
    'controller_serial':
        "Atlas Copco controller serial this tool is paired with (e.g. 'ES512'). "
        "Auto-filled from Open Protocol pull when available; blank otherwise.",
    'firmware':
        "Controller firmware version, e.g. '3.14.11.35838'. Sourced "
        "automatically from MID 0040 when applicable.",
    'protocol_version':
        "Open Protocol revision the controller is speaking (e.g. '1.7'). "
        "Detected from the first byte-pair on connect.",
    'total_tightenings':
        "Cumulative tightenings the tool has performed in its lifetime "
        "(sometimes called 'cycle count'). Sourced from MID 0040 "
        "byte-offset 60 in the Open Protocol frame.",
    'tightenings_since_svc':
        "Tightenings performed since the last calibration / service. "
        "Used to schedule the next service. Sourced from MID 0040.",
    'tightening_id':
        "Unique identifier of the last tightening result "
        "(e.g. 'T20260828-001'). Sourced from MID 0060; blank if no result is known.",
    'tightening_status':
        "Pass/fail state of the last tightening. "
        "'OK' = torque and angle both inside tolerance, "
        "'NOK' = one or both out of tolerance, "
        "'Aborted' = tightening was stopped manually or by the controller.",
    'notes':
        "Free-text note about this maintenance event. Anything that helps "
        "when reading the row back later — e.g. 'Reset torque to 60 Nm after "
        "operator complaint'.",

    # SEARCH form
    'executor_search':
        "Case-insensitive substring match on the executor field. "
        "'mur' matches 'Sandro Mura'.",
    'status_search':
        "Case-insensitive substring match on the status field. "
        "'cancel' matches 'Cancelled'.",
    'sap_order_search':
        "Case-insensitive substring match on the SAP order number. "
        "'FST' matches 'FSTDEC8556'.",
    'tool_serial_search':
        "Case-insensitive substring match on the tool serial number.",
    'tightening_status_search':
        "Exact match on the tightening status (OK / NOK / Aborted) — leave as "
        "the default blank option for 'don't care'.",
    'max_rows':
        "Cap on the number of rows returned (default 200, max 5000). "
        "Lower this if your browser gets slow on big result sets.",
    'work_date_from':
        "Only return work performed on or after this date (inclusive).",
    'work_date_to':
        "Only return work performed on or before this date (inclusive).",

    # ---- Setup tab ----
    'setup_mode':
        "Database mode. 'Local SQLite' stores everything in a single file "
        "in the project folder and needs no auth. 'Remote database' lets "
        "you point at a PostgreSQL / MySQL / MSSQL server.",
    'setup_driver':
        "SQLAlchemy dialect + driver. Pick the one that matches your DB "
        "server. The matching driver package must be installed "
        "(see requirements.txt for the optional ones). "
        "Supported: 'postgresql' (psycopg2-binary / psycopg), "
        "'mysql+pymysql' (pymysql), 'mssql+pyodbc' (pyodbc + ODBC driver), "
        "'oracle+oracledb' (oracledb), 'snowflake' (snowflake-sqlalchemy), "
        "'duckdb' (duckdb_engine). Default port is auto-filled per choice.",
    'setup_host':
        "Hostname or IP of the database server. Use 'localhost' or "
        "127.0.0.1 if the DB runs on the same machine as the dashboard.",
    'setup_port':
        "TCP port the DB server listens on. Defaults: 5432 (PostgreSQL), "
        "3306 (MySQL), 1433 (MSSQL).",
    'setup_login':
        "Database username. Use a dedicated, low-privilege user if your "
        "DB team supports it; don't reuse 'sa' / 'postgres' / 'root'.",
    'setup_password':
        "Password for the database user above. Stored in plain text inside "
        "db_config.json (gitignored). Do NOT commit. The value gets "
        "URL-encoded automatically.",
    'setup_database':
        "Database / schema name on the server. Must exist before the "
        "dashboard can connect.",
    'setup_sqlite_path':
        "Path to the SQLite database file, relative to the project folder "
        "(e.g. './database.sqlite') or absolute. The parent folder is "
        "created automatically on save.",
}


def _safe_df(rows: list[dict], index_col: str) -> pd.DataFrame:
    """Build a DataFrame keyed on `index_col`, even when `rows` is empty.

    `pd.DataFrame([])` returns a DataFrame with no columns, so calling
    `.set_index('foo')` on it raises KeyError. This helper guarantees the
    requested index column exists (with the right dtype) even on an empty
    list, so the chart / dataframe renders a clean empty axis instead of
    crashing the dashboard.
    """
    if not rows:
        # Build a zero-row frame with just the index column so set_index works.
        return pd.DataFrame({index_col: pd.Series([], dtype='object')}).set_index(index_col)
    return pd.DataFrame(rows).set_index(index_col)


# ---------------------------------------------------------------------------
# Page setup + DB
# ---------------------------------------------------------------------------

# Required fields for the Create form. tool_type is included because
# every real maintenance entry is tied to a specific tool model and
# the Open Protocol pull can populate it automatically.
_REQUIRED_CREATE = ("tool_serial", "tool_type", "work_date", "executor")
_REQUIRED_LABELS = {
    "tool_serial": "Tool serial",
    "tool_type":   "Tool type",
    "work_date":   "Work date",
    "executor":    "Executor",
}


def _missing_required(payload, required=None):
    """Return list of required field names whose value is empty/None/blank."""
    if required is None:
        required = _REQUIRED_CREATE
    missing = []
    for k in required:
        v = payload.get(k)
        if v is None:
            missing.append(k)
            continue
        if isinstance(v, str) and not v.strip():
            missing.append(k)
    return missing


def _fetch_via_op(st_session_state):
    """Fetch tool data from the controller and populate session_state."""
    host = (st_session_state.get("op_host") or "").strip() or "10.0.0.1"
    port_raw = st_session_state.get("op_port") or 4545
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 4545
    try:
        from app.protocol import fetch_tool_data
        parsed = fetch_tool_data(host, port)
        st_session_state["op_tool_serial"]       = parsed.get("tool_serial", "")
        st_session_state["op_tool_type"]         = parsed.get("tool_type", "")
        st_session_state["op_controller_serial"] = parsed.get("controller_serial", "")
        st_session_state["op_firmware"]          = parsed.get("firmware", "")
        st_session_state["op_total_tightenings"] = int(parsed.get("total_tightenings") or 0)
        st_session_state["op_raw_response"]      = parsed.get("raw_response", "")
        st_session_state.pop("op_last_error", None)
        st.success(
            "Fetched from " + str(host) + ":" + str(port) +
            " - tool_type=" + repr(parsed.get("tool_type", ""))
        )
    except Exception as exc:
        st_session_state["op_last_error"] = (
            "Could not fetch from " + str(host) + ":" + str(port) +
            " - " + exc.__class__.__name__ + ": " + str(exc)
        )
        st.error(st_session_state["op_last_error"])


st.set_page_config(
    page_title=f'Tool CRUD Dashboard v{__version__}',
        page_icon='🔧',
    layout='wide',
    initial_sidebar_state='expanded',
)

# Create tables on first import (idempotent).
init_db()


# ---------------------------------------------------------------------------
# Sidebar — live DB stats + platform info + version
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    with st.sidebar:
        # Brand block — Atlas Copco logo (bundled in assets/atlas_copco_logo.png),
        # restored in v1.2.8 after the v1.2.3 logo-lightening pass. The page_icon
        # and the main header keep the wrench emoji for a quieter look; the
        # sidebar is the place where the logo doesn't conflict with the title.
        # The if/else keeps the app bootable if the asset file is missing
        # (e.g. running just the .py without the repo folder).
        try:
            st.image(str(LOGO_FILE), width=160)
        except (FileNotFoundError, TypeError, ValueError):
            st.markdown(f'### {WRENCH} Tool CRUD Dashboard')
        st.markdown(f'### {version_string()}')
        st.caption(f'Platform: **{PLATFORM}**')
        st.caption(f'DB: `{get_database_url()}`')
        if is_sqlite(get_database_url()):
            db_file = PROJECT_DIR / 'database.sqlite'
            if db_file.exists():
                size_kb = db_file.stat().st_size / 1024
                st.caption(f'SQLite file: {size_kb:.1f} KB')

        st.divider()
        st.markdown('### Database')
        snap = kpis.snapshot()
        st.metric('Records',  snap['total_rows'])
        st.metric('OK rate',  f"{snap['ok_rate'] * 100:.1f} %")
        st.metric('Avg torque', f"{snap['avg_torque']:.2f} Nm")
        if snap['last_seen_at']:
            st.caption(f'Last entry: {snap["last_seen_at"]}')

        _render_auth_widget()

        st.divider()
        st.markdown('### Refresh')
        if st.button('Reload KPIs', width="stretch"):
            st.cache_data.clear()
            st.rerun()


def _render_auth_widget() -> None:
    """Sidebar widget that unlocks destructive actions for the session.

    When the user is authenticated, a countdown shows how long the unlock
    lasts (default 10 minutes), and a 'Lock now' button is available.
    When locked, a password field + 'Authenticate' button appear; the
    password is verified against the active hash (default: 'Atlas123!',
    override via OPEN_PROTOCOL_PASSWORD_HASH env var).
    """
    st.divider()
    st.markdown('### 🔒 Destructive actions')
    if auth.is_authenticated(st.session_state):
        remaining = auth.remaining_seconds(st.session_state)
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        st.success(f'Unlocked · {mins}m {secs:02d}s remaining')
        c1, c2 = st.columns(2)
        if c1.button('Re-check', width='stretch'):
            # Re-extends the TTL by AUTH_TTL_SECONDS.
            st.session_state['auth_expires_at'] = time.time() + auth.AUTH_TTL_SECONDS
            st.rerun()
        if c2.button('Lock now', width='stretch'):
            auth.clear_auth(st.session_state)
            st.rerun()
    else:
        pw = st.text_input(
            'Password',
            type='password',
            placeholder='Enter password to unlock',
            key='sidebar_auth_pw',
            label_visibility='collapsed',
        )
        if st.button('Authenticate', type='primary', width='stretch'):
            if auth.authenticate(st.session_state, pw):
                st.session_state.pop('sidebar_auth_pw', None)
                st.rerun()
            else:
                st.error('Wrong password.')


# ---------------------------------------------------------------------------
# Helper renderers
# ---------------------------------------------------------------------------
def _status_emoji(s: str) -> str:
    return protocol.status_emoji(s)


def _render_tool_data(parsed: dict) -> None:
    st.success(
        f"Connected to {st.session_state.get('ip', '?')}:"
        f"{st.session_state.get('port', '?')}  ·  "
        f"response {len(parsed.get('raw_response', ''))} chars"
    )
    st.markdown(f'### Tool data  ·  *{parsed.get("tool_serial", "—")}*')
    left, right = st.columns(2)
    with left:
        st.markdown('**Tool**')
        st.code(
            f"Tool serial             : {parsed.get('tool_serial', '—')}\n"
            f"Total tightenings       : {parsed.get('total_tightenings', 0):,}\n"
            f"Tightenings since svc   : {parsed.get('tightenings_since_svc', 0):,}\n"
            f"Calibration value       : {parsed.get('calibration_value', '—')}\n"
            f"Last calibration date   : {parsed.get('last_calibration_date', '—')}\n"
            f"Last service date       : {parsed.get('last_service_date', '—')}"
        )
    with right:
        st.markdown('**Controller**')
        st.code(
            f"Controller serial       : {parsed.get('controller_serial', '—')}\n"
            f"Firmware                : {parsed.get('firmware', '—')}\n"
            f"Protocol version        : {parsed.get('protocol_version', '—')}"
        )
    with st.expander('Raw MID 0040 response'):
        st.text(parsed.get('raw_response', ''))


def _render_tightening(parsed: dict) -> None:
    st.markdown(f'### Last tightening  ·  '
                f'{_status_emoji(parsed.get("tightening", "?"))} '
                f'{parsed.get("tightening", "—")}')
    emoji_t = _status_emoji(parsed.get('torque_status', ''))
    emoji_a = _status_emoji(parsed.get('angle_status', ''))
    st.code(
        f"Cell ID                 : {parsed.get('cell_id', '—')}\n"
        f"Channel ID              : {parsed.get('channel_id', '—')}\n"
        f"Job number              : {parsed.get('job_number', '—')}\n"
        f"Tightening ID           : {parsed.get('tightening_id', '—')}\n"
        f"Batch counter           : {parsed.get('batch_counter', '—')}\n"
        f"Batch status            : {parsed.get('batch_status', '—')}\n"
        f"Timestamp               : {parsed.get('time_stamp', '—')}\n"
        f"Torque                  : {parsed.get('torque_value', '—')} Nm   "
        f"({emoji_t} {parsed.get('torque_status', '—')})\n"
        f"    target / min / max  : "
        f"{parsed.get('torque_target', '—')}  /  "
        f"{parsed.get('torque_min', '—')}  /  "
        f"{parsed.get('torque_max', '—')}\n"
        f"Angle                   : {parsed.get('angle_value', '—')} deg   "
        f"({emoji_a} {parsed.get('angle_status', '—')})\n"
        f"    target / min / max  : "
        f"{parsed.get('angle_target', '—')}  /  "
        f"{parsed.get('angle_min', '—')}  /  "
        f"{parsed.get('angle_max', '—')}"
    )


# ---------------------------------------------------------------------------
# Tab 1 - Live
# ---------------------------------------------------------------------------
def render_live_tab() -> None:
    st.header('Live data')
    st.caption('Reads from the controller on each click. Socket is fresh '
               'every time, so it is safe to spam the buttons.')

    ip   = st.text_input('IP address of controller', key='ip',
                         placeholder='10.0.0.1')
    port = st.text_input('Port of controller',       key='port',
                         value='4545')

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button('Get tool data', width="stretch"):
            if not ip or not port:
                st.error('Enter both IP and port first.')
            else:
                with st.spinner('Fetching MID 0040 ...'):
                    try:
                        parsed = protocol.fetch_tool_data(ip, int(port))
                        parsed['protocol_version'] = ''
                        try:
                            v = protocol.fetch_controller_version(ip, int(port))
                            parsed['protocol_version'] = (
                                f"{v.get('major','?')}."
                                f"{v.get('minor','?')}."
                                f"{v.get('patch','?')}"
                            )
                        except Exception:
                            pass
                        parsed['controller_ip']   = ip
                        parsed['controller_port'] = int(port)
                        parsed['work_date']       = date.today()
                        _render_tool_data(parsed)
                        saved, status = crud.create_log_from_controller(parsed)
                        if status == 'CREATED':
                            st.toast(f"Saved new record #{saved.get('id')}", icon='✅')
                        else:
                            st.toast('Already on record (no change)', icon='🔁')
                    except (socket.timeout, OSError, protocol.ProtocolError) as e:
                        st.error(f'Network error: {e}')
    with c2:
        if st.button('Get controller info', width="stretch"):
            if not ip or not port:
                st.error('Enter both IP and port first.')
            else:
                with st.spinner('Fetching MIDs 0080 / 0010 / 0030 ...'):
                    try:
                        with st.container(border=True):
                            st.markdown('#### MID 0080  ·  Protocol version')
                            v = protocol.fetch_controller_version(ip, int(port))
                            st.code(f"{v.get('major','?')}."
                                    f"{v.get('minor','?')}."
                                    f"{v.get('patch','?')}")
                        with st.container(border=True):
                            st.markdown('#### MID 0010  ·  Parameter set IDs')
                            ids = protocol.fetch_parameter_set_ids(ip, int(port))
                            st.code(f"Count: {ids['count']}\n"
                                    f"IDs:   " + ' · '.join(ids['ids']))
                        with st.container(border=True):
                            st.markdown('#### MID 0030  ·  Job list')
                            jobs = protocol.fetch_job_list(ip, int(port))
                            st.code(f"Count: {jobs['count']}\n"
                                    f"Jobs:  " + ' · '.join(jobs['ids']))
                    except (socket.timeout, OSError, protocol.ProtocolError) as e:
                        st.error(f'Network error: {e}')
    with c3:
        if st.button('Get last tightening', width="stretch"):
            if not ip or not port:
                st.error('Enter both IP and port first.')
            else:
                with st.spinner('Fetching MID 0060 ...'):
                    try:
                        t = protocol.fetch_last_tightening(ip, int(port))
                        _render_tightening(t)
                        # Auto-save into a log row.
                        t['controller_ip']   = ip
                        t['controller_port'] = int(port)
                        t['work_date']       = date.today()
                        saved, status = crud.create_log_from_controller(t)
                        if status == 'CREATED':
                            st.toast(f"Saved new record #{saved.get('id')}", icon='✅')
                        else:
                            st.toast('Already on record (no change)', icon='🔁')
                    except (socket.timeout, OSError, protocol.ProtocolError) as e:
                        st.error(f'Network error: {e}')




# ---------------------------------------------------------------------------
# Tab 2 - CRUD
# ---------------------------------------------------------------------------
def render_crud_tab() -> None:
    st.header('CRUD — maintenance log')
    st.caption('Create / read / update / delete rows in `maintenance_log`. '
               'Same schema as the XLSX template + all Open Protocol fields.')

    sub = st.tabs(['Create', 'Read · Browse', 'Update', 'Delete'])
    with sub[0]:
        _render_create_form()
    with sub[1]:
        _render_browse_tab()
    with sub[2]:
        _render_update_form()
    with sub[3]:
        _render_delete_form()


def _render_browse_tab() -> None:
    """Read-only row-by-row browser with first/prev/next/last + jump-to-id.

    Ordering is newest-first (descending id). Buttons disable at the
    ends. State lives in `st.session_state['browse_id']` so navigating
    across other tabs and back doesn't lose the cursor. Robust against
    id gaps caused by deletes — cursor is always a real id, not an offset.
    """
    total = crud.count_logs()
    if total == 0:
        st.info('No records yet — create one or pull from controller.')
        return

    # Initialise / repair the cursor.
    if 'browse_id' not in st.session_state or not st.session_state['browse_id']:
        first = crud.get_first_log()
        st.session_state['browse_id'] = first['id'] if first else None
    cur_id = st.session_state.get('browse_id')
    cur_row = crud.get_log(cur_id) if cur_id else None
    if cur_row is None:
        # The id we were on no longer exists (e.g. it was deleted).
        cur = crud.get_last_log()
        cur_id = cur['id'] if cur else None
        cur_row = cur
        st.session_state['browse_id'] = cur_id
    if cur_row is None:
        st.warning('No rows available.')
        return

    newest = crud.get_first_log()
    oldest = crud.get_last_log()
    is_newest = bool(newest and cur_row['id'] == newest['id'])
    is_oldest = bool(oldest and cur_row['id'] == oldest['id'])

    st.caption(
        f"Row **id = {cur_row['id']}**  ·  total **{total}** rows  ·  "
        f"newest? {'✅' if is_newest else '—'}  ·  oldest? {'✅' if is_oldest else '—'}  ·  "
        "browse order: newest → oldest"
    )

    # Navigation buttons
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    if c1.button('� First (newest)', disabled=is_newest, width='stretch'):
        if newest:
            st.session_state['browse_id'] = newest['id']
            st.rerun()
    if c2.button('◀ Newer', disabled=is_newest, width='stretch'):
        nxt = crud.get_prev_log(cur_row['id'])  # default desc: 'prev' in id = newer in time
        if nxt:
            st.session_state['browse_id'] = nxt['id']
            st.rerun()
    if c3.button('Older ▶', disabled=is_oldest, width='stretch'):
        prv = crud.get_next_log(cur_row['id'])  # default desc: 'next' in id = older in time
        if prv:
            st.session_state['browse_id'] = prv['id']
            st.rerun()
    if c4.button('⏭ Last (oldest)', disabled=is_oldest, width='stretch'):
        if oldest:
            st.session_state['browse_id'] = oldest['id']
            st.rerun()

    # Jump-to-id
    j1, j2 = st.columns([4, 1])
    target_id = j1.number_input(
        'Jump to id',
        min_value=1,
        max_value=10_000_000,
        step=1,
        value=int(cur_row['id']),
        label_visibility='collapsed',
    )
    if j2.button('Go', width='stretch'):
        target = crud.get_log(int(target_id))
        if target:
            st.session_state['browse_id'] = target['id']
            st.rerun()
        else:
            st.error(f'No row with id = {int(target_id)}.')

    st.divider()
    st.markdown('##### Current row')

    # Pretty-print work_date as dd/mm/yyyy without mutating the dict in place.
    # Inline helper so we don't need to import a non-existent dates module
    # in the current codebase; if `app.dates.to_ddmmyyyy` is added later,
    # this branch keeps working with a graceful fallback.
    display = dict(cur_row)
    if display.get('work_date'):
        try:
            wd_raw = display['work_date']
            if isinstance(wd_raw, str) and len(wd_raw) == 10 and wd_raw[4] == '-':
                # ISO YYYY-MM-DD -> dd/mm/yyyy
                display['work_date'] = f"{wd_raw[8:10]}/{wd_raw[5:7]}/{wd_raw[0:4]}"
            else:
                display['work_date'] = str(wd_raw)
        except Exception:
            pass
    st.dataframe(pd.DataFrame([display]), width='stretch', hide_index=True)

    with st.expander('Raw fields (JSON)'):
        st.json(cur_row)


def _render_create_form() -> None:
    """New maintenance entry.

    Required fields: tool_serial, tool_type, work_date, executor.
    The Create button stays disabled until all four are filled.
    A 'Fetch from controller' button uses Open Protocol MID 0040 to
    auto-populate tool_serial + tool_type + controller_serial +
    firmware + total_tightenings from the live controller.

    Server-side: app.crud.create_log() re-checks the same required
    fields and returns 'MISSING' if any are blank, so callers that
    bypass the UI cannot save empties either.
    """
    # --- Controller connection fields (used by Fetch button) ------------
    with st.expander("Controller connection (used by Fetch)", expanded=False):
        cc1, cc2 = st.columns(2)
        with cc1:
            st.text_input(
                "Controller host / IP",
                key="op_host",
                value=st.session_state.get("op_host", "10.0.0.1"),
                placeholder="10.0.0.1",
                help=_HELP.get("setup_host",
                                "IP / hostname of the Atlas Copco controller."),
            )
        with cc2:
            st.number_input(
                "Controller port",
                key="op_port",
                min_value=1, max_value=65535,
                value=int(st.session_state.get("op_port", 4545) or 4545),
                step=1,
                help="Open Protocol TCP port (default 4545).",
            )
        if st.button("Fetch from controller (MID 0040)", type="secondary"):
            _fetch_via_op(st.session_state)

    # --- Required-field hint banner -------------------------------------
    st.info(
        "Required: " + ", ".join(_REQUIRED_LABELS[k] for k in _REQUIRED_CREATE) +
        ". Click 'Fetch from controller' above to auto-fill tool "
        "serial, tool type, controller serial and firmware via "
        "Open Protocol MID 0040."
    )

    with st.form("create_form", clear_on_submit=False):
        st.subheader("New maintenance entry")

        c1, c2, c3 = st.columns(3)
        with c1:
            executor = st.text_input(
                "Executor *", placeholder="First Last",
                help=_HELP["executor"],
            )
            sap_order = st.text_input(
                "SAP order", placeholder="0000000000",
                help=_HELP["sap_order"],
            )
            sap_status_options = st.text_input(
                "SAP status options", placeholder="optional",
                help=_HELP["sap_status_options"],
            )
        with c2:
            status_options = [
                "Finished", "In progress", "Cancelled", "Waiting for parts",
            ]
            status = st.selectbox(
                "Status", status_options, index=0, help=_HELP["status"],
            )
            work_date = st.date_input(
                "Work date (dd/mm/yyyy) *",
                value=date.today(),
                help=_HELP["work_date"],
            )
        with c3:
            start_time = st.text_input(
                "Start time", placeholder="HH:MM",
                help=_HELP["start_time"],
            )
            end_time = st.text_input(
                "End time", placeholder="HH:MM",
                help=_HELP["end_time"],
            )

        st.markdown("**Tool identity (required) **")
        t1, t2, t3 = st.columns(3)
        with t1:
            tool_serial = st.text_input(
                "Tool serial *",
                value=st.session_state.get("op_tool_serial") or "",
                placeholder="A4411212",
                help=_HELP["tool_serial"],
            )
        with t2:
            tool_type = st.text_input(
                "Tool type *",
                value=st.session_state.get("op_tool_type") or "",
                placeholder="ETX / Tensor / QST",
                help=_HELP["tool_type"],
            )
        with t3:
            controller_serial = st.text_input(
                "Controller serial",
                value=st.session_state.get("op_controller_serial") or "",
                placeholder="optional",
                help=_HELP["controller_serial"],
            )

        st.markdown("**Optional Open Protocol fields**")
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            firmware = st.text_input(
                "Firmware",
                value=st.session_state.get("op_firmware") or "",
                help=_HELP["firmware"],
            )
            protocol_version = st.text_input(
                "Protocol version", help=_HELP["protocol_version"],
            )
        with d2:
            total_tightenings = st.number_input(
                "Total tightenings",
                min_value=0, step=1,
                value=int(st.session_state.get("op_total_tightenings") or 0),
                help=_HELP["total_tightenings"],
            )
            tightenings_since_svc = st.number_input(
                "Since service", min_value=0, step=1, value=0,
                help=_HELP["tightenings_since_svc"],
            )
        with d3:
            tightening_id = st.text_input(
                "Tightening ID", help=_HELP["tightening_id"],
            )
            tightening_status = st.selectbox(
                "Tightening status",
                ["", "OK", "NOK", "Aborted"], index=0,
                help=_HELP["tightening_status"],
            )
        with d4:
            cell_id = st.text_input("Cell ID", placeholder="optional")
            job_number = st.text_input("Job number", placeholder="optional")

        notes = st.text_area("Notes", help=_HELP["notes"])

        payload = {
            "executor"             : executor,
            "status"               : status,
            "sap_order"            : sap_order,
            "sap_status_options"   : sap_status_options,
            "work_date"            : work_date,
            "start_time"           : start_time,
            "end_time"             : end_time,
            "tool_serial"          : tool_serial,
            "tool_type"            : tool_type,
            "controller_serial"    : controller_serial,
            "firmware"             : firmware,
            "protocol_version"     : protocol_version,
            "total_tightenings"    : total_tightenings,
            "tightenings_since_svc": tightenings_since_svc,
            "tightening_id"        : tightening_id,
            "tightening_status"    : tightening_status,
            "cell_id"              : cell_id,
            "job_number"           : job_number,
            "notes"                : notes,
            "source"               : "manual",
        }
        missing = _missing_required(payload)
        ready = not missing
        label = "Create record" if ready else (
            "Fill required: " + ", ".join(_REQUIRED_LABELS[m] for m in missing)
        )
        if st.form_submit_button(label, disabled=not ready, type="primary"):
            saved, status_flag = crud.create_log(payload)
            if status_flag == "CREATED":
                st.success("Created record #" + str(saved.get("id")))
                for k in (
                    "op_tool_serial", "op_tool_type",
                    "op_controller_serial", "op_firmware",
                    "op_total_tightenings", "op_raw_response",
                ):
                    st.session_state.pop(k, None)
                st.rerun()
            elif status_flag == "MISSING":
                st.error(
                    "Server-side validation failed - missing: "
                    + ", ".join(saved.get("missing", []))
                )
            else:
                st.warning("Duplicate - that natural key already exists.")


def _render_update_form() -> None:
    rows = crud.list_logs(limit=50)
    if not rows:
        st.info('No records yet.')
        return
    id_to_label = {r['id']: f"#{r['id']} · {r['work_date']} · "
                              f"{r.get('executor') or '?'} · "
                              f"{r.get('sap_order') or '?'}"
                   for r in rows}
    choice = st.selectbox('Pick a row to edit', options=list(id_to_label),
                          format_func=lambda i: id_to_label[i])
    row = next(r for r in rows if r['id'] == choice)

    with st.form('update_form'):
        c1, c2, c3 = st.columns(3)
        with c1:
            executor  = st.text_input('Executor', value=row.get('executor', '') or '', help=_HELP['executor'])
            sap_order = st.text_input('SAP order', value=row.get('sap_order', '') or '', help=_HELP['sap_order'])
        with c2:
            status_opts = ['Finished', 'In progress', 'Cancelled', 'Waiting for parts']
            current = row.get('status') or 'Finished'
            try:
                idx = status_opts.index(current)
            except ValueError:
                idx = 0
            status = st.selectbox('Status', status_opts, index=idx, help=_HELP['status'])
            wd = row.get('work_date') or date.today().isoformat()
            try:
                wd_val = datetime.strptime(wd, '%Y-%m-%d').date()
            except ValueError:
                wd_val = date.today()
            work_date = st.date_input('Date', value=wd_val, help=_HELP['work_date'])
        with c3:
            start_time = st.text_input('Start time', value=row.get('start_time', '') or '', help=_HELP['start_time'])
            end_time   = st.text_input('End time',   value=row.get('end_time', '') or '', help=_HELP['end_time'])

        notes = st.text_area('Notes', value=row.get('notes', '') or '', help=_HELP['notes'])
        if st.form_submit_button('Update'):
            updated = crud.update_log(choice, {
                'executor':  executor,
                'status':    status,
                'sap_order': sap_order,
                'work_date': work_date,
                'start_time': start_time,
                'end_time':   end_time,
                'notes':     notes,
            })
            if updated:
                st.success(f"Updated record #{choice}")
                st.rerun()


def _render_delete_form() -> None:
    rows = crud.list_logs(limit=200)
    if not rows:
        st.info('No records yet.')
        return
    id_to_label = {r['id']: f"#{r['id']} · {r['work_date']} · "
                              f"{r.get('executor') or '?'} · "
                              f"{r.get('sap_order') or '?'}"
                   for r in rows}
    targets = st.multiselect('Rows to delete', options=list(id_to_label),
                             format_func=lambda i: id_to_label[i])
    confirm_box = st.checkbox(
        'I am sure — delete these rows permanently',
        key='delete_confirm_box',
    )
    confirmation_text = st.text_input(
        'Type DELETE to confirm',
        key='delete_confirm_text',
        placeholder='DELETE',
        help='This is a second confirmation gate. Type the word DELETE (case-sensitive) to enable the button.',
    )
    text_ok = (confirmation_text or '').strip() == 'DELETE'

    authed = auth.is_authenticated(st.session_state)
    if not authed:
        st.warning('🔒 Destructive actions are locked. Enter the password below to unlock delete for this session.')
        pw = st.text_input(
            'Password',
            type='password',
            key='delete_auth_pw',
            placeholder='Password to unlock delete',
            label_visibility='collapsed',
        )
        if st.button('Authenticate', key='delete_auth_btn', type='primary', width='stretch'):
            if auth.authenticate(st.session_state, pw):
                st.session_state.pop('delete_auth_pw', None)
                st.rerun()
            else:
                st.error('Wrong password.')

    ready = bool(targets) and confirm_box and text_ok and authed
    label = 'Delete selected' if ready else 'Complete all confirmations to delete'
    if st.button(label, disabled=not ready, type='primary', width='stretch'):
        for tid in targets:
            crud.delete_log(tid)
        # Clear the confirm text so a follow-up accidental click requires
        # re-typing DELETE.
        st.session_state.pop('delete_confirm_text', None)
        st.success(f'Deleted {len(targets)} row(s).')
        st.rerun()


# ---------------------------------------------------------------------------
# Tab 3 - KPIs
# ---------------------------------------------------------------------------
def render_kpis_tab() -> None:
    st.header('KPIs')
    snap = kpis.snapshot()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Records',          snap['total_rows'])
    c2.metric('Tightenings',      snap['total_tightenings'])
    c3.metric('OK rate',          f"{snap['ok_rate'] * 100:.1f} %")
    c4.metric('Avg torque',       f"{snap['avg_torque']:.2f} Nm")

    st.divider()

    a, b = st.columns(2)
    with a:
        st.markdown('##### Daily activity (last 30 days)')
        daily = _safe_df(snap['daily'], 'day')
        st.line_chart(daily, height=240)
    with b:
        st.markdown('##### Monthly activity (last 12 months)')
        monthly = _safe_df(snap['monthly'], 'month')
        st.bar_chart(monthly, height=240)

    st.divider()

    d, e = st.columns(2)
    with d:
        st.markdown('##### Top executors')
        df_exec = _safe_df(snap['top_executors'], 'executor')
        st.dataframe(df_exec, width="stretch")
    with e:
        st.markdown('##### Top tools')
        df_tool = _safe_df(snap['top_tools'], 'tool_serial')
        st.dataframe(df_tool, width="stretch")

    st.divider()
    st.markdown('##### Status distribution')
    df_st = _safe_df(snap['status_dist'], 'status')
    st.bar_chart(df_st, height=200)

    alerts = snap['calibration_alerts']
    if alerts:
        st.divider()
        st.markdown(f'##### Calibration overdue ({len(alerts)} tool(s))')
        st.dataframe(pd.DataFrame(alerts), width="stretch")


# ---------------------------------------------------------------------------
# Tab 4 - Search
# ---------------------------------------------------------------------------
def render_search_tab() -> None:
    st.header('Search')
    with st.form('search_form'):
        c1, c2, c3 = st.columns(3)
        with c1:
            executor      = st.text_input('Executor contains', help=_HELP['executor_search'])
            status        = st.text_input('Status contains', help=_HELP['status_search'])
            sap_order     = st.text_input('SAP order contains', help=_HELP['sap_order_search'])
        with c2:
            tool_serial   = st.text_input('Tool serial contains', help=_HELP['tool_serial_search'])
            tightening_st = st.selectbox('Tightening status',
                                          ['', 'OK', 'NOK', 'Aborted'], index=0,
                                          help=_HELP['tightening_status_search'])
            limit         = st.number_input('Max rows', min_value=1, max_value=5000,
                                             value=200, step=50,
                                             help=_HELP['max_rows'])
        with c3:
            d_from = st.date_input('Work date from', value=None, help=_HELP['work_date_from'])
            d_to   = st.date_input('Work date to',   value=None, help=_HELP['work_date_to'])

        go = st.form_submit_button('Search')

    if not go:
        st.caption('Fill in any subset of filters and press Search.')
        return

    rows = crud.search_logs(
        executor=executor,
        status=status,
        sap_order=sap_order,
        tool_serial=tool_serial,
        work_date_from=d_from if d_from else None,
        work_date_to=d_to if d_to else None,
        tightening_status=tightening_st,
        limit=int(limit),
    )
    df = pd.DataFrame(rows)
    st.caption(f'{len(df)} row(s) matched.')
    st.dataframe(df, width="stretch", hide_index=True)
    if not df.empty:
        st.download_button(
            'Download as CSV',
            df.to_csv(index=False).encode('utf-8'),
            file_name=f'maintenance_log_{datetime.now():%Y%m%d_%H%M%S}.csv',
            mime='text/csv',
        )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Tab 5 - Setup (database configuration)
# ---------------------------------------------------------------------------
def render_setup_tab() -> None:
    """UI for choosing Local SQLite vs Remote database, and persisting the
    choice to db_config.json. After a successful save the engine is
    reset and the schema is re-applied against the new DB.
    """
    from app import config as _appcfg
    from app.db import reset_engine, init_db
    from app.paths import get_database_url

    st.header('Setup · database connection')
    st.caption(
        'Pick **Local SQLite** for a single-file database in the project '
        'folder, or **Remote** to point at a PostgreSQL / MySQL / MSSQL '
        'server. Saved to `db_config.json` (gitignored). Env var '
        '`DATABASE_URL` always wins over the file.'
    )

    cfg = _appcfg.load_db_config()
    current_url = get_database_url()

    s1, s2 = st.columns(2)
    s1.markdown('**Current connection**')
    s1.code(_appcfg.redact_password(current_url), language='text')
    s2.markdown('**Config file**')
    s2.code(_appcfg.redact_password(str(_appcfg.CONFIG_FILE)), language='text')

    with st.form('setup_form'):
        mode = st.radio(
            'Mode',
            ['Local SQLite', 'Remote database'],
            index=0 if cfg.get('mode', 'local') == 'local' else 1,
            horizontal=True,
            help=_HELP['setup_mode'],
        )
        if mode == 'Local SQLite':
            sqlite_path = st.text_input(
                'SQLite file path',
                value=cfg.get('sqlite_path', './database.sqlite'),
                help=_HELP['setup_sqlite_path'],
            )
            payload = {'mode': 'local', 'sqlite_path': sqlite_path}
        else:
            drivers = ['postgresql', 'mysql+pymysql', 'mssql+pyodbc']
            cur_driver = cfg.get('driver', 'postgresql')
            driver = st.selectbox(
                'Database type',
                drivers,
                index=drivers.index(cur_driver) if cur_driver in drivers else 0,
                format_func=lambda d: _appcfg.DRIVER_LABELS.get(d, d),
                help=_HELP['setup_driver'],
            )
            host = st.text_input(
                'Host',
                value=cfg.get('host', 'localhost'),
                placeholder='db.example.com or 10.0.0.1',
                help=_HELP['setup_host'],
            )
            port = st.number_input(
                'Port',
                min_value=1, max_value=65535,
                value=int(cfg.get('port', _appcfg.DEFAULT_REMOTE_PORTS[driver])),
                step=1,
                help=_HELP['setup_port'],
            )
            login = st.text_input(
                'Login',
                value=cfg.get('login', ''),
                placeholder='op_dashboard',
                help=_HELP['setup_login'],
            )
            password = st.text_input(
                'Password',
                value=cfg.get('password', ''),
                placeholder='********',
                type='password',
                help=_HELP['setup_password'],
            )
            database = st.text_input(
                'Database name',
                value=cfg.get('database', ''),
                placeholder='open_protocol',
                help=_HELP['setup_database'],
            )
            payload = {
                'mode'    : 'remote',
                'driver'  : driver,
                'host'    : host,
                'port'    : int(port),
                'login'   : login,
                'password': password,
                'database': database,
            }

        test_btn = st.form_submit_button('Test connection')

    if test_btn:
        ok, msg = _appcfg.test_connection(payload)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    # ----- Auth + confirmation gate for Save (outside the form so the
    # Save button can be conditionally enabled/disabled) -----
    st.divider()
    st.markdown('#### Confirm and save')

    authed = auth.is_authenticated(st.session_state)
    if not authed:
        st.warning(
            '🔒 Destructive actions are locked. Enter the password below to '
            'unlock Save for this session.'
        )
        pw = st.text_input(
            'Password',
            type='password',
            key='setup_auth_pw',
            placeholder='Password to unlock Save',
            label_visibility='collapsed',
        )
        if st.button('Authenticate', key='setup_auth_btn', type='primary', width='stretch'):
            if auth.authenticate(st.session_state, pw):
                st.session_state.pop('setup_auth_pw', None)
                st.rerun()
            else:
                st.error('Wrong password.')

    confirm_box = st.checkbox(
        'I understand this changes the active database',
        key='setup_confirm_box',
    )
    confirmation_text = st.text_input(
        'Type CHANGE to confirm',
        key='setup_confirm_text',
        placeholder='CHANGE',
        help='Second confirmation gate. Type the word CHANGE (case-sensitive) to enable the Save button.',
    )
    text_ok = (confirmation_text or '').strip() == 'CHANGE'

    ready = confirm_box and text_ok and authed
    label = 'Save and switch database' if ready else 'Complete all confirmations to save'
    if st.button(label, disabled=not ready, type='primary', width='stretch'):
        try:
            url_preview = _appcfg.build_database_url(payload)
        except ValueError as exc:
            st.error(f'Cannot save: {exc}')
            return
        try:
            _appcfg.save_db_config(payload)
        except OSError as exc:
            st.error(f'Could not write config: {exc}')
            return
        reset_engine()
        try:
            init_db()
        except Exception as exc:
            st.warning(f'Saved, but init_db() failed on the new DB: {exc}')
        # Clear the confirm text so a follow-up accidental click requires
        # re-typing CHANGE.
        st.session_state.pop('setup_confirm_text', None)
        st.success(f'Saved. Now using {_appcfg.redact_password(url_preview)}.')
        st.rerun()

    _render_supported_databases_panel(_appcfg)
    _render_password_section()


def _render_supported_databases_panel(_appcfg) -> None:
    """Reference panel shown under the Setup form: every DB system the
    dashboard can talk to, with driver name, default port, example URL,
    pip-install command, and notes. Helps users see the door is wider
    than the 3-option selectbox above (the extra drivers can be enabled
    by editing db_config.json directly or via DATABASE_URL env var).
    """
    st.divider()
    with st.expander(
        'Supported database systems (reference panel)',
        expanded=False,
    ):
        st.caption(
            'Only the three drivers in the **Database type** dropdown are exposed '
            'in the form. The other systems below work too — set them via the '
            '`DATABASE_URL` env var or by editing `db_config.json` directly.'
        )
        for spec in _appcfg.SUPPORTED_DATABASES:
            port = spec['default_port']
            port_str = str(port) if port else '—'
            st.markdown(
                f"#### {spec['display_name']}"
                f"  ·  `{spec['key']}`  ·  default port **{port_str}**"
            )
            st.markdown(
                f"- **Example URL:** `{spec['example_url']}`"
            )
            st.markdown(
                f"- **Install driver:** `{spec['pip_install']}`"
            )
            st.markdown(
                f"- **Notes:** {spec['notes']}"
            )
            st.divider()


def _render_destructive_gate(scope_key: str, checkbox_label: str, typed_word: str) -> None:
    """Shared sidebar-gate UI used by delete / save-db / change-password.

    Renders an inline password box + Authenticate button if the session
    is not yet unlocked, plus the confirmation checkbox + typed
    confirmation word fields. Caller checks
    `auth.is_authenticated(st.session_state)` to decide whether to
    enable the actual action button.
    """
    authed = auth.is_authenticated(st.session_state)
    if not authed:
        pw = st.text_input(
            'Password to unlock destructive actions',
            type='password',
            key=f'{scope_key}_inline_pw',
            placeholder='Enter password',
            label_visibility='collapsed',
        )
        if st.button('Authenticate', key=f'{scope_key}_inline_btn', type='primary'):
            if auth.authenticate(st.session_state, pw):
                st.session_state.pop(f'{scope_key}_inline_pw', None)
                st.rerun()
            else:
                st.error('Wrong password.')
    st.checkbox(checkbox_label, key=f'{scope_key}_confirm_box')
    st.text_input(
        f'Type {typed_word} to confirm',
        key=f'{scope_key}_confirm_text',
        placeholder=typed_word,
        help=f'Second confirmation gate. Type the word {typed_word} (case-sensitive) to enable the action button.',
    )


def _render_password_section() -> None:
    """Password change / reset panel in the Setup tab.

    Behaviour:
        * **Default password** (`Atlas123!`) is shown when no
          `auth_config.json` file exists on disk. This is the
          "When reinstalling then use standard password" path.
        * **Custom password** is shown when `auth_config.json` is
          present and contains a non-default hash.
        * Both the **Change password** and **Reset to standard**
          buttons are gated by the same destructive-action gate used
          for delete records / save DB config (sidebar unlock +
          confirmation checkbox + typed confirmation word).
    """
    import app.password_config as pwcfg  # local import keeps top of file tidy

    st.divider()
    st.subheader(f'{WRENCH} Destructive-action password')

    # Status banner: tell the operator which password is currently active.
    if pwcfg.is_using_default():
        st.info(
            f'Active password: **default** (`{auth.DEFAULT_PASSWORD}`). '
            'This is what fresh installs / `--recreate-venv` always start with.'
        )
    else:
        st.success(
            'Active password: **custom** (stored in `auth_config.json`). '
            'Use Reset below to go back to the default.'
        )
    st.caption(
        'Resolution order: `OPEN_PROTOCOL_PASSWORD_HASH` env var '
        '→ `auth_config.json` → built-in default. Delete '
        '`auth_config.json` to reset to default manually.'
    )

    # Re-use the existing destructive-action gate.
    _render_destructive_gate(
        scope_key='pw',
        checkbox_label='I understand this changes the destructive-action password',
        typed_word='RESET',
    )

    pw_authed = auth.is_authenticated(st.session_state)
    confirm_box = bool(st.session_state.get('pw_confirm_box'))
    confirm_text = (st.session_state.get('pw_confirm_text') or '').strip()
    text_ok = confirm_text == 'RESET'
    pw_gated = pw_authed and confirm_box and text_ok

    # ----------------------- Change password -----------------------
    with st.expander('Change password', expanded=False):
        with st.form('pw_change_form', clear_on_submit=False):
            current_pw = st.text_input(
                'Current password',
                type='password',
                key='pw_current',
                placeholder='Current destructive-action password',
                help='Enter the password that is currently active (default or custom).',
            )
            new_pw = st.text_input(
                'New password',
                type='password',
                key='pw_new',
                placeholder='New password (min 8 chars)',
                help='Pick a new password. Minimum 8 characters.',
            )
            confirm_pw = st.text_input(
                'Confirm new password',
                type='password',
                key='pw_confirm',
                placeholder='Type the new password again',
                help='Must match the new password field above.',
            )
            pw_long_enough = len(new_pw or '') >= 8
            pw_match = bool(new_pw) and new_pw == confirm_pw
            form_ready = pw_long_enough and pw_match
            ready = pw_gated and form_ready
            label = 'Save new password' if ready else 'Complete all confirmations to save'
            if st.form_submit_button(label, disabled=not ready, type='primary'):
                if not auth.verify_password(current_pw or ''):
                    st.error('Current password is incorrect.')
                else:
                    try:
                        pwcfg.save_password_hash(pwcfg.hash_password(new_pw))
                    except (ValueError, OSError) as exc:
                        st.error(f'Could not save: {exc}')
                    else:
                        st.session_state.pop('pw_new', None)
                        st.session_state.pop('pw_confirm', None)
                        st.success('Password updated. Next destructive action uses the new password.')
                        st.rerun()

    # ----------------------- Reset to standard -----------------------
    with st.expander('Reset to standard password (`Atlas123!`)', expanded=False):
        st.caption(
            'Removes `auth_config.json` so the built-in default is used again. '
            'Same behaviour as a fresh install / `--recreate-venv`.'
        )
        if not pw_gated:
            st.button(
                'Reset to standard password',
                disabled=True,
                key='pw_reset_btn',
                help='Unlock destructive actions in the sidebar first and complete the RESET confirmation.',
            )
        else:
            if st.button(
                'Reset to standard password',
                type='primary',
                key='pw_reset_btn',
            ):
                removed = pwcfg.clear_password_hash()
                if removed:
                    st.success('`auth_config.json` removed. Default `Atlas123!` is now active.')
                else:
                    st.info('Already using the default password — nothing to remove.')
                # Clear confirm so a follow-up accidental click requires
                # re-typing RESET.
                st.session_state.pop('pw_confirm_text', None)
                st.rerun()


# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # Header: simple title + caption stack (logo removed in v1.2.3 after
    # it visually competed with the title; the wrench emoji is back).
    st.title('🔧 Tool CRUD Dashboard')
    st.caption(
        f'**v{__version__}**  ·  Platform: {PLATFORM}  ·  '
        f'DB: {"SQLite (local)" if is_sqlite(get_database_url()) else get_database_url()}'
)

    render_sidebar()

    tab_live, tab_crud, tab_kpi, tab_search, tab_setup = st.tabs(
        ['Live data', 'CRUD', 'KPIs', 'Search', 'Setup'])
    with tab_live:   render_live_tab()
    with tab_crud:   render_crud_tab()
    with tab_kpi:    render_kpis_tab()
    with tab_search: render_search_tab()
    with tab_setup:  render_setup_tab()


main()
