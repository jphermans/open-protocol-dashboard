## [1.0.6] - 2026-08-28

### Added
- Every form input in the CRUD and Search tabs now shows a hover/tooltip
  `help=` text explaining what to fill in, derived from the
  'TMC Herstellingen ASML' XLSX column semantics (and the Open
  Protocol MID 0040 / 0060 byte layout for the tool fields).
  Tooltips cover all 31 widgets across:
    * CREATE form — Executor, SAP order, SAP status options, Status,
      Date, Start time, End time, Tool serial, Controller serial,
      Firmware, Protocol version, Total tightenings, Since service,
      Tightening ID, Tightening status, Notes.
    * UPDATE form — same 7 work-order fields + Notes.
    * SEARCH form — Executor / Status / SAP order / Tool serial
      "contains" boxes, Tightening status select, Max rows cap,
      Work date from / to.
- The tooltip text is centralised in a single `_HELP` dict at the top
  of `app/streamlit_app.py`. Adding tooltips to new widgets is now:
  `_HELP['new_key'] = '...'` once, then pass `help=_HELP['new_key']`
  to the widget.

### Notes
- Pure UI change — no schema change, no behaviour change, no
  dependency change. PATCH bump per SemVer (copy / wording /
  tooltip addition).


## [1.0.5] - 2026-08-28

### Fixed
- `python3 run.py --version` crashed with `ModuleNotFoundError: No
  module named 'sqlalchemy'` when run with a Python that did not have
  the project requirements installed (most commonly: system Python
  on macOS instead of `.venv/bin/python`). Root cause: the `--version`
  branch imported `version_string` from the `app` package, which
  transitively imported `app.db`, which imports `sqlalchemy`. Fix:
  two complementary changes.
    1. `run.py` now reads `__version__` directly from `app/__init__.py`
       via the stdlib `ast` module — zero `app` / `sqlalchemy` /
       `streamlit` imports needed. `run.py --version` now works on any
       Python 3.10+, regardless of whether the venv is set up.
    2. `app/__init__.py` re-exports (`init_db`, `session_scope`,
       `PROJECT_DIR`, `PLATFORM`, `get_database_url`, `is_sqlite`) are
       now lazy via PEP 562 module `__getattr__`. Importing
       `version_string` or `__version__` alone is now side-effect-free;
       `sqlalchemy` is loaded only when CRUD / KPI code actually needs
       it.

### Changed
- `app/__init__.py` docstring expanded to document the lazy-import
  contract so future contributors know they can `from app import
  __version__` without pulling in the whole stack.


## [1.0.4] - 2026-08-28

### Changed
- Project is now English-only. All UI labels, form labels, default
  status values, and inline comments are in English.
- Form-field label changes (`app/streamlit_app.py`):
    * `Executor (UITVOERDER)`              → `Executor`
    * `Status (AFWERING STATUS)`           → `Status`
    * `Date (DATUM)`                       → `Date`
    * `Start time (BEGIN)`                 → `Start time`
    * `End time (EIND)`                    → `End time`
    * `SAP order (ORDER SAP)`              → `SAP order`
- Default status options changed from Dutch to English:
    * `['Afgewerkt', 'In uitvoering',
         'Geannuleerd', 'Wachten op onderdelen']`
       → `['Finished', 'In progress',
           'Cancelled', 'Waiting for parts']`
- Executor placeholder changed: `Voornaam Achternaam` → `First Last`.
- README.md and CHANGELOG.md prose cleaned up — no remaining Dutch
  work-order column references (`UITVOERDER`, `AFWERING STATUS`, etc.).
- `app/models.py` docstring rewritten to describe the work-order
  columns using their English equivalents; inline `# DUTCH` comments
  removed from individual column definitions (the section header now
  just reads `XLSX-derived work-order columns`).

### Notes
- This is a copy/UI-change PATCH bump — no schema change, no behaviour
  change, no dependency change. Existing rows in the DB still hold
  whatever status string was written at the time (mix of Dutch and
  English is harmless for full-text filtering; use the status filter
  on the Search tab to scope by either language).


## [1.0.3] - 2026-08-28

### Changed
- `app/streamlit_app.py` form-field placeholders no longer reference
  shop-floor data. Replacements:
    * `placeholder='Sandro Mura'`        → `placeholder='Voornaam Achternaam'`
      (Executor / VOORNAAM + ACHTERNAAM field — placeholder text only)
    * `placeholder='192.168.188.120'`    → `placeholder='10.0.0.1'`
      (Controller IP field — the previous value was the actual
      production controller IP and would have leaked the shop-floor
      network topology into the public repo)
    * `placeholder='FSTDEC8556'`         → `placeholder='0000000000'`
      (SAP order field — the previous value looked like a real
      SAP order number)
  No functional change; this is purely a hygiene / privacy cleanup so
  nothing shop-floor-specific ends up in the public repository.
  (Reported by the user before the public release.)


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
  XLSX template 'TMC Herstellingen ASML' (executor, status, SAP order,
  SAP status options, work date, start time, end time) plus every Open
  Protocol field (MID 0040 / 0060 / 0080).
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
