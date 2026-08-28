## [1.0.2] - 2026-08-28

### Fixed
- `app/streamlit_app.py` `render_kpis_tab` crashed with
  `KeyError: "None of ['executor'] are in the columns"` (and the same
  pattern for `day`, `month`, `tool_serial`, `status`) on a fresh empty
  database. Root cause: `pd.DataFrame([])` returns a zero-column frame,
  so `.set_index('foo')` raises KeyError when the underlying kpis list
  is empty. Fix: introduced a small helper `_safe_df(rows, index_col)`
  that builds an empty frame with the requested index column when the
  list is empty, and used it at all five call sites in the KPI tab so
  the dashboard renders clean empty axes instead of crashing.
  (Reported by the user on macOS with Python 3.14 against a freshly
  cloned repo.)


## [1.0.0] - 2026-08-28

### Added
- **CRUD layer** for maintenance log entries (`app/crud.py`).
- **SQLAlchemy ORM** model `MaintenanceLog` with the full schema from the
  XLSX template 'TMC Herstellingen ASML' (Dutch columns: UITVOERDER,
  AFWERING STATUS, ORDER SAP, STATUS OPTIES SAP, DATUM, BEGIN, EIND)
  plus every Open Protocol field (MID 0040 / 0060 / 0080).
- **Remote DB support** via `DATABASE_URL` env var. Default is a local
  SQLite file in the project folder; PostgreSQL, MySQL, MSSQL also work
  once the matching driver is added to `requirements.txt`.
- **KPI dashboard** (`app/kpis.py`): records, OK rate, average torque,
  daily/monthly trends, top executors, top tools, calibration-overdue
  alerts.
- **Search + CSV export** in the UI.
- **Single-file cross-platform launcher** `run.py` — detects OS
  (Windows / WSL / Linux / macOS), locates Python 3.10+, builds a venv,
  installs dependencies, opens the browser.
- **Versioning** — `app/__version__ = "1.0.0"`, surfaced in the sidebar,
  printed by `run.py --version`, documented in this changelog.
- **`.env.example`** with ready-to-copy DATABASE_URL samples.
- **`docs/`** folder for project artefacts.

### Changed
- Project split into a proper Python package: `app/` (protocol, db,
  models, crud, kpis, streamlit_app).
- Single Streamlit entry point at `app/streamlit_app.py`.
- Old monolithic `streamlit_app.py`, `start.sh`, `start.bat`,
  `launcher.py` retained as thin wrappers but `run.py` is now the
  recommended entry point.

### Fixed
- `kpis.py` `f-string` syntax (5 lines).
- `crud.py` PostgreSQL ON CONFLICT path now commits the duplicate row
  reload correctly.
