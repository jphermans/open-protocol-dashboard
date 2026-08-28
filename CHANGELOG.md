# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).


## [1.0.1] - 2026-08-28

### Fixed
- `app/kpis.py` `trend_by_week` and `trend_by_month` crashed with
  `AttributeError: 'NoneType' object has no attribute 'isocalendar'` on
  SQLite when at least one row had a NULL `work_date`. Root cause: the
  SELECT listed `work_date` alongside `COUNT(id)` without a `GROUP BY`
  clause, so SQLite returned one aggregated row with `work_date=NULL`.
  Fix: added `.group_by(MaintenanceLog.work_date)` to both queries, plus
  a defensive `if d is None: continue` guard in the iteration loops so
  any future NULL slipping through the filter is skipped silently instead
  of crashing the dashboard. (Reported by the user running v1.0.0 on
  macOS with Python 3.14.)


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
