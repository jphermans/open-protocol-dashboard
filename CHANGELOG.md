## [1.2.0] - 2026-08-28

### Added
- **Password + confirmation gate for destructive actions.** Two actions
  in the dashboard now require authentication before they can fire:
    * Deleting one or more maintenance-log records.
    * Switching the database backend (Local SQLite ↔ Remote,
      host/port/login/password/db name).
  Both gates require **all three** of:
    * Session-wide unlock (via the new sidebar "🔒 Destructive
      actions" widget) **or** inline password entry inside the form.
    * A confirmation checkbox ("I am sure — delete these rows
      permanently" / "I understand this changes the active database").
    * A typed confirmation word — **DELETE** for delete, **CHANGE**
      for save — entered into a separate text field (case-sensitive,
      cleared after each successful action to prevent accidental
      repeat-clicks).
- **New module `app/auth.py`** providing:
    * `DEFAULT_PASSWORD = "Atlas123!"` (per spec).
    * `verify_password(pw)` — constant-time SHA-256 check against the
      active hash (default = hash of `Atlas123!`).
    * `authenticate(session_state, pw)` — grants a session-wide unlock
      that lasts `AUTH_TTL_SECONDS = 600` (10 minutes). The unlock is
      re-extendable from the sidebar via the **Re-check** button.
    * `clear_auth()` — wipes the unlock immediately (used by the
      sidebar **Lock now** button and on TTL expiry).
    * `is_authenticated()` / `remaining_seconds()` — read-side helpers.
  Operator-supplied override via the `OPEN_PROTOCOL_PASSWORD_HASH` env
  var (SHA-256 hex of the salted password); generation recipe is
  documented in the module docstring.
- **Sidebar "🔒 Destructive actions" widget** with two states:
    * **Locked** — password field + Authenticate button.
    * **Unlocked** — countdown ("Unlocked · Xm YYs remaining"),
      **Re-check** (extend TTL) and **Lock now** buttons.
- Inline password fields + Authenticate buttons inside the Delete
  sub-tab and the Setup save panel, so a one-off destructive action
  can be performed even without using the sidebar widget first.

### Security notes
- Passwords are hashed (SHA-256 + static salt) before comparison.
  Plaintext passwords live only in the Streamlit text-input widget
  for the duration of one form submission and are never written to
  disk, never logged, never echoed back in the UI.
- The session unlock TTL is 10 minutes by default — adjust via
  `AUTH_TTL_SECONDS` in `app/auth.py`.
- `Atlas123!` is a placeholder. Operators are strongly encouraged to
  override it with a stronger password before deploying to a
  multi-user environment. The override mechanism is the
  `OPEN_PROTOCOL_PASSWORD_HASH` env var; a UI control for changing
  the password at runtime is a candidate for a future MINOR-bump
  release.

### Notes
- MINOR bump per SemVer (1.1.3 → 1.2.0): new feature (auth
  subsystem) added without breaking existing functionality. Delete
  and Save both still work exactly as before for users who already
  know the password — the gate is additive, not a behaviour change
  for trusted single-user setups.


## [1.1.3] - 2026-08-28

### Added
- **Browse sub-tab** inside the CRUD tab. New `Read · Browse` panel
  between Create and Update that lets the user step through the
  database one row at a time with arrows:
    * `⏮ First (newest)` — jump to the newest row
    * `◀ Newer` — one row newer in time
    * `Older ▶` — one row older in time
    * `⏭ Last (oldest)` — jump to the oldest row
    * `Jump to id` + `Go` — type any id, go straight to it
  Buttons disable at the ends. State lives in
  `st.session_state['browse_id']` so navigating across tabs and back
  doesn't lose the cursor. Robust against id gaps caused by deletes
  (cursor is always a real id, not an offset).
- Five new helpers in `app/crud.py` powering the Browse tab:
    * `get_log_by_offset(offset)` — fetch the row at position N
      (0-indexed, default newest-first). Uses `ORDER BY id LIMIT 1
      OFFSET N` so it survives deleted-id gaps.
    * `get_prev_log(current_id)` — neighbour with the nearest larger
      id (newer in time when browse order is desc).
    * `get_next_log(current_id)` — neighbour with the nearest smaller
      id (older in time).
    * `get_first_log()` — newest row.
    * `get_last_log()` — oldest row.
  All five respect the `order_desc` flag so callers can flip the
  direction without changing the UI layout.

### Notes
- PATCH bump per SemVer (1.1.2 → 1.1.3): no schema change, no API
  change; new CRUD sub-tab and 5 new CRUD helpers.
- The Browse sub-tab renders `work_date` as `dd/mm/yyyy` for human
  reading while keeping the underlying value ISO `YYYY-MM-DD` in the
  raw-fields expander.


## [1.1.2] - 2026-08-28

### Added
- **Example placeholders** on every remote-database Setup-tab field, so
  the user can see what a typical value looks like before typing:
    * Host — `db.example.com or 10.0.0.1`
    * Login — `op_dashboard`
    * Password — `********` (masked)
    * Database name — `open_protocol`
- **Human-readable labels** in the **Database type** dropdown. The
  raw SQLAlchemy prefix (`postgresql`, `mysql+pymysql`, `mssql+pyodbc`)
  is now shown as `PostgreSQL (psycopg2-binary / psycopg)` etc., via the
  new `DRIVER_LABELS` dict in `app/config.py`.
- **Reference panel** under the Setup form (`Supported database
  systems (reference panel)` expander). For every DB system the
  dashboard can talk to it lists:
    * SQLAlchemy key (`sqlite`, `postgresql`, `mysql+pymysql`,
      `mssql+pyodbc`, `oracle+oracledb`, `snowflake`, `duckdb`)
    * Display name + default port
    * Example URL (password redacted)
    * Exact `pip install` command for the driver
    * Notes (ODBC requirement for MSSQL, Oracle `service_name`,
      Snowflake account locator, DuckDB OLAP angle, ...)
- `SUPPORTED_DATABASES` list (7 entries) added to `app/config.py` —
  drives the reference panel. Adding a new driver is now a one-line
  dict append, no UI changes needed.

### Notes
- PATCH bump per SemVer (1.1.1 → 1.1.2): no schema or API change,
  the selectbox still exposes the original three drivers; the
  reference panel is read-only documentation that helps users
  realise the door is wider than the visible list.
- The extra drivers (`oracle+oracledb`, `snowflake`, `duckdb`) are
  reachable today via `DATABASE_URL` env var or by hand-editing
  `db_config.json`; promoting them to the selectbox is a future
  MINOR-bump UI change.


## [1.1.1] - 2026-08-28

### Changed
- **Dates displayed as `dd/mm/yyyy`** everywhere in the UI (work-date
  input, KPI chart axis labels, live and search tables, update form
  pre-fill). Internal storage stays ISO `YYYY-MM-DD` so SQL range
  queries keep working. Helper functions `to_ddmmyyyy()` and
  `from_ddmmyyyy()` in the new `app/dates.py` are the single source
  of truth.
- **Required-field guard** on Create and Update forms. The minimum
  required set is `tool_serial`, `work_date`, `executor`. The Save
  button is `disabled` and labelled `Fill required fields to save`
  until the form is complete, with live red error hints on each
  missing field. CRUD `create_log()` / `update_log()` raise
  `ValueError` server-side as a backstop, rendered as `st.error`
  in the UI.

### Fixed
- Empty-DB crash: `pd.DataFrame([])` no longer triggers `KeyError`
  on `set_index('xxx')`. The `_safe_df()` helper, added in v1.0.2
  for the KPI tab, is now also used on the Search results and the
  Live tab.

### Notes
- PATCH bump per SemVer (1.1.0 → 1.1.1): UX improvement only, no
  schema or API change.
- Pre-existing rows whose `status` was written in Dutch
  (e.g. `Afgewerkt`) are untouched. To migrate them to English,
  ask for a one-click "Rename old status values" button in a future
  PATCH.


## [1.1.0] - 2026-08-28

### Added
- **Setup tab** in the Streamlit UI for configuring the database at
  runtime. The new `Setup · database connection` tab lets the user
  pick **Local SQLite** vs **Remote database** (PostgreSQL /
  MySQL+PyMySQL / MSSQL+PyODBC) and fill in:
    * Local mode — SQLite file path (relative or absolute).
    * Remote mode — driver, host, port, login, password, database name.
  Two buttons: **Test connection** (verifies the config can reach
  the DB without committing it) and **Save** (writes `db_config.json`,
  resets the SQLAlchemy engine, re-runs `init_db()` against the new
  target, reruns the page so the new connection takes effect
  immediately).
- **Config file resolution** in `app/paths.py:get_database_url()`:
    1. `DATABASE_URL` env var (highest priority — preserves existing
       `.env` / `run.py --db ...` behaviour).
    2. `db_config.json` on disk (whatever the Setup tab last saved).
    3. Built-in default: local SQLite in the project folder.
- New module `app/config.py` providing:
    * `load_db_config()` / `save_db_config()` — JSON on disk,
      atomic write via temp-file + rename.
    * `build_database_url(cfg)` — turns the config dict into a
      SQLAlchemy URL string with proper `urllib.parse.quote_plus` on
      user / password.
    * `redact_password(url)` — masks the password segment of a URL
      for safe display in the UI / logs.
    * `test_connection(cfg)` — actually opens a connection to verify
      the config is valid; returns (ok, message).
- New function `app.db.reset_engine()` that drops the cached engine
  + session factory so the next call to `get_engine()` re-resolves
  the URL and creates a fresh engine against the new DB.
- All 8 new Setup-tab form fields carry tooltips in the existing
  `_HELP` dict (`setup_mode`, `setup_driver`, `setup_host`,
  `setup_port`, `setup_login`, `setup_password`, `setup_database`,
  `setup_sqlite_path`).

### Notes
- This is a new feature, backward-compatible (default behaviour
  unchanged when no config file exists). Bumps 1.0.6 -> 1.1.0,
  MINOR per SemVer.
- **Security:** the password is stored in plain text inside
  `db_config.json` because the Setup tab has to feed it back into
  the UI on the next page load. `db_config.json` is now
  `.gitignore`d, but you should still treat the file as a secret:
  don't commit it, don't back it up to a non-encrypted share, and
  prefer using a low-privilege, database-local user.


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
