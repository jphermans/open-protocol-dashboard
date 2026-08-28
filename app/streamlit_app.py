"""Open Protocol CRUD dashboard — Streamlit entry point.

Run with:
    streamlit run app/streamlit_app.py
or (preferred):
    python run.py

Layout:
  * Title + version banner
  * Sidebar: live DB stats + platform info + refresh button
  * Tab 1 - Live: controller pull (MID 0040 / 0060 / 0080 / 0010 / 0030)
  * Tab 2 - CRUD: create / read / update / delete maintenance log rows
  * Tab 3 - KPIs: snapshot metrics + charts
  * Tab 4 - Search: filter the log table and export CSV
"""
from __future__ import annotations

import socket
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
import app.crud as crud
import app.kpis as kpis
import app.protocol as protocol


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
st.set_page_config(
    page_title=f'Open Protocol Dashboard v{__version__}',
    page_icon='\U0001f527',
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

        st.divider()
        st.markdown('### Refresh')
        if st.button('Reload KPIs', width="stretch"):
            st.cache_data.clear()
            st.rerun()


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

    mode = st.radio('Mode', ['Create', 'Update', 'Delete'], horizontal=True)

    if mode == 'Create':
        _render_create_form()
    elif mode == 'Update':
        _render_update_form()
    else:
        _render_delete_form()


def _render_create_form() -> None:
    with st.form('create_form', clear_on_submit=True):
        st.subheader('New maintenance entry')
        c1, c2, c3 = st.columns(3)
        with c1:
            executor = st.text_input('Executor', placeholder='First Last')
            sap_order = st.text_input('SAP order', placeholder='0000000000')
            sap_status_options = st.text_input('SAP status options', placeholder='optional')
        with c2:
            status_options = ['Finished', 'In progress', 'Cancelled', 'Waiting for parts']
            status = st.selectbox('Status', status_options, index=0)
            work_date = st.date_input('Date', value=date.today())
        with c3:
            start_time = st.text_input('Start time', placeholder='HH:MM')
            end_time   = st.text_input('End time',   placeholder='HH:MM')

        st.markdown('**Optional Open Protocol fields**')
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            tool_serial = st.text_input('Tool serial')
            controller_serial = st.text_input('Controller serial')
        with d2:
            firmware = st.text_input('Firmware')
            protocol_version = st.text_input('Protocol version')
        with d3:
            total_tightenings = st.number_input('Total tightenings', min_value=0, step=1, value=0)
            tightenings_since_svc = st.number_input('Since service', min_value=0, step=1, value=0)
        with d4:
            tightening_id = st.text_input('Tightening ID')
            tightening_status = st.selectbox('Tightening status', ['', 'OK', 'NOK', 'Aborted'], index=0)

        notes = st.text_area('Notes')

        if st.form_submit_button('Create'):
            payload = {
                'executor'             : executor,
                'status'               : status,
                'sap_order'            : sap_order,
                'sap_status_options'   : sap_status_options,
                'work_date'            : work_date,
                'start_time'           : start_time,
                'end_time'             : end_time,
                'tool_serial'          : tool_serial,
                'controller_serial'    : controller_serial,
                'firmware'             : firmware,
                'protocol_version'     : protocol_version,
                'total_tightenings'    : total_tightenings,
                'tightenings_since_svc': tightenings_since_svc,
                'tightening_id'        : tightening_id,
                'tightening_status'    : tightening_status,
                'notes'                : notes,
                'source'               : 'manual',
            }
            saved, status_flag = crud.create_log(payload)
            if status_flag == 'CREATED':
                st.success(f"Created record #{saved.get('id')}")
            else:
                st.warning('Duplicate — that natural key already exists.')


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
            executor  = st.text_input('Executor', value=row.get('executor', '') or '')
            sap_order = st.text_input('SAP order', value=row.get('sap_order', '') or '')
        with c2:
            status_opts = ['Finished', 'In progress', 'Cancelled', 'Waiting for parts']
            current = row.get('status') or 'Finished'
            try:
                idx = status_opts.index(current)
            except ValueError:
                idx = 0
            status = st.selectbox('Status', status_opts, index=idx)
            wd = row.get('work_date') or date.today().isoformat()
            try:
                wd_val = datetime.strptime(wd, '%Y-%m-%d').date()
            except ValueError:
                wd_val = date.today()
            work_date = st.date_input('Date', value=wd_val)
        with c3:
            start_time = st.text_input('Start time', value=row.get('start_time', '') or '')
            end_time   = st.text_input('End time',   value=row.get('end_time', '') or '')

        notes = st.text_area('Notes', value=row.get('notes', '') or '')
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
    confirm = st.checkbox('I am sure — delete these rows permanently')
    if st.button('Delete selected', disabled=not (targets and confirm)):
        for tid in targets:
            crud.delete_log(tid)
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
            executor      = st.text_input('Executor contains')
            status        = st.text_input('Status contains')
            sap_order     = st.text_input('SAP order contains')
        with c2:
            tool_serial   = st.text_input('Tool serial contains')
            tightening_st = st.selectbox('Tightening status',
                                          ['', 'OK', 'NOK', 'Aborted'], index=0)
            limit         = st.number_input('Max rows', min_value=1, max_value=5000,
                                             value=200, step=50)
        with c3:
            d_from = st.date_input('Work date from', value=None)
            d_to   = st.date_input('Work date to',   value=None)

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
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    st.title(f'🛠 Open Protocol CRUD Dashboard')
    st.caption(
        f'**v{__version__}**  ·  Platform: {PLATFORM}  ·  '
        f'DB: {"SQLite (local)" if is_sqlite(get_database_url()) else get_database_url()}'
    )

    render_sidebar()

    tab_live, tab_crud, tab_kpi, tab_search = st.tabs(
        ['Live data', 'CRUD', 'KPIs', 'Search'])
    with tab_live:   render_live_tab()
    with tab_crud:   render_crud_tab()
    with tab_kpi:    render_kpis_tab()
    with tab_search: render_search_tab()


main()
