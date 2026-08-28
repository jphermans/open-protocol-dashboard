## [1.2.7] - 2026-08-28

### Fixed
- **App startup crash in Setup tab** - `NameError: name 'WRENCH' is not defined`
  when opening the Setup tab. The `WRENCH` emoji constant was referenced
  by `_render_password_section()` (added in v1.2.4) but was never defined.
  Fixed by adding `WRENCH = '\U0001F527'` (codepoint U+1F527, "\xf0\x9f\x94\xa7"
  in UTF-8) at module scope in `app/streamlit_app.py`, alongside the
  other constants. Centralising all emoji icons at module scope means
  similar `NameError`s can't recur.

## [1.2.6] - 2026-08-28

### Fixed
- **App startup crash** - ImportError on macOS / Linux / Windows:
  \`ImportError: cannot import name 'get_engine' from 'app.paths'\`.
  The v1.2.5 migration added a duplicate \`init_db()\` at the bottom of
  \`app/db.py\` that incorrectly did \`from app.paths import get_engine\`,
  but \`get_engine\` lives in \`app/db.py\` itself, not in \`app/paths.py\`.
  The duplicate also shadowed the working \`init_db()\` higher up via
  Python last-wins, so the broken copy was the one that ran. Fixed by:
    * Removing the duplicate.
    * Extending the surviving \`init_db()\` to call \`_ensure_tool_type_column(engine)\`
      so the v1.2.5 tool_type migration still runs on every startup.

## [1.2.5] - 2026-08-28

### Added
- **`tool_type` column in the `maintenance_log` table** (VARCHAR(32),
  nullable). Atlas Copco tool model / type identifier (e.g. `ETX`,
  `Tensor`, `QST`). Auto-populated from Open Protocol MID 0040
  (bytes 36-56, revision-dependent).
- **Live "Fetch from controller (MID 0040)" button** in the Create
  form. Operators enter the controller host + port and click
  Fetch; the dashboard calls `app.protocol.fetch_tool_data()` over
  TCP, parses the response, and pre-fills:
    * Tool serial *
    * Tool type *
    * Controller serial
    * Firmware
    * Total tightenings
  The fields default to whatever the controller returned but remain
  fully editable.
- **`_REQUIRED_CREATE` tuple + `_missing_required()` helper** at the
  top of `app/streamlit_app.py`. The Create button stays disabled
  until all four required fields are filled; the label flips from
  `Create record` to `Fill required: Tool serial, Tool type, ...`
  so the operator knows exactly what is missing.
- **`_fetch_via_op()` helper** in `app/streamlit_app.py` - the
  session-state-aware wrapper that runs the Open Protocol fetch
  and caches the parsed values for the next form render.
- **`tool_type` tooltip** in the centralised `_HELP` dict, sourced
  from the same XLSX + Open Protocol context as the other entries.

### Fixed
- **"I still can create an empty record"** - the previous Create
  form had no required-field guard. Now `tool_serial`, `tool_type`,
  `work_date` and `executor` are mandatory at both the UI layer (the
  Create button is `disabled` and the label shows the missing field
  names) and the server layer (`crud.create_log()` returns
  `('MISSING', missing=[...])` if any required field is blank, so a
  caller that bypasses the UI gate still cannot save an empty row).

### Changed
- **`parse_mid_0040()`** now extracts `tool_type` from raw bytes
  36-56 (20 ASCII chars). Tolerant of revisions where the field is
  absent: returns `'—'` rather than raising.
- **`MaintenanceLog.as_display_dict()`** includes `tool_type`.

### Notes
- **In-place schema migration**: `_ensure_tool_type_column()` runs
  once at startup, inspecting `maintenance_log` for an existing
  `tool_type` column and issuing an `ALTER TABLE ... ADD COLUMN`
  statement only when missing. Idempotent for SQLite, PostgreSQL,
  MySQL/MariaDB, and MSSQL. Existing databases created on v1.2.4
  gain the column automatically on first launch of v1.2.5.

## [1.2.4] - 2026-08-28

### Added
- **Password change / reset panel in the Setup tab.** Operators can now
  change the destructive-action password from the UI; the value
  survives an app restart and a venv rebuild. The change flow
  re-uses the same sidebar-gate as Delete / Save-database:
  session-unlock + checkbox + typed confirmation word (`RESET`).
    * **Change password** expander: enter current password, new
      password (min 8 chars), and confirmation. The current password
      is re-verified before the new hash is written.
    * **Reset to standard password (`Atlas123!`)** expander: deletes
      `auth_config.json` so a fresh install / `--recreate-venv` /
      manual `rm auth_config.json` always comes back to the factory
      default. This is the explicit "When reinstalling then use
      standard password" path.
- **New module `app/password_config.py`** owns the on-disk storage:
  atomic JSON write to `auth_config.json`, validation of the stored
  hash, and a three-tier resolution helper
  (`env > file > default`) used by `app.auth.get_password_hash()`.
- **Shared helper `_render_destructive_gate(scope_key, checkbox_label,
  typed_word)`** in `streamlit_app.py` so delete / save-db /
  change-password all paint the same gate UI from one place.

### Changed
- `app/auth.py::get_password_hash()` now consults
  `app.password_config` between the env-var override and the
  built-in default. A missing or malformed `auth_config.json` is
  treated as "use default" so the dashboard stays bootable; the
  operator can repair from the Setup tab.
- `.gitignore`: `auth_config.json` added (gitignored, like
  `db_config.json`).
- `__version__` bumped `1.2.3` → `1.2.4` (MINOR per SemVer:
  backward-compatible feature add; no behaviour change for the
  default password).

### Notes
- The custom password is stored as SHA-256 with the existing
  static salt (`op_dash:`). Same hashing as the env-var override,
  same strength, same caveats in `app/auth.py`'s docstring.
- Resetting to standard removes the file entirely — it does not
  write a copy of the default hash, so the three-tier resolution
  still lands on the default branch on the next call.
- The change-password flow is gated by the destructive-action
  password itself. If the active password is forgotten, the
  fallback is `rm auth_config.json` (or `--recreate-venv`) which
  brings `Atlas123!` back — by design.


## [1.2.3] - 2026-08-28

### Fixed
- **`AttributeError: module 'hashlib' has no attribute 'compare_digest'`
  on every destructive action** (delete record, save database config).
  Root cause: `app/auth.py::verify_password()` called
  `hashlib.compare_digest(...)` for constant-time comparison — but
  `compare_digest` lives in the **`hmac`** module, not `hashlib`.
  (`hashlib.sha256`, `hashlib.md5`, etc. are correct — only
  `compare_digest` got moved to `hmac` in Python 3.3.) The bug shipped
  silently in v1.2.0 because the original test box had a `hashlib`
  monkey-patch and never hit the real AttributeError. Fix:
  `import hmac` + `return hmac.compare_digest(candidate, expected)`.

### Changed
- **Atlas Copco logo removed from the in-app surfaces** (page favicon,
  sidebar top, main header). The asset at
  `assets/atlas_copco_logo.png` is **kept** — still bundled into
  PyInstaller builds and still displayed at the top of `README.md`.
  Restored surfaces:
    * `page_icon` back to the `🔧` wrench emoji.
    * `render_sidebar()` top slot is now an empty comment placeholder.
    * `main()` header is again a plain `st.title('🔧 Tool CRUD
      Dashboard')` + caption stack (no columns-with-logo layout).
- `__version__` bumped `1.2.2` → `1.2.3` (PATCH per SemVer: UI tweak
  + bugfix, no behaviour change for the happy path).

### Notes
- `app/paths.py`'s `LOGO_FILE` constant is kept so a future release can
  opt back into the logo with a one-line change.
- The bug class here is worth flagging: anything that imports `hashlib`
  and then needs constant-time comparison must `import hmac` (or use
  `secrets.compare_digest`, which is the modern alias in Py 3.5+).


## [1.2.2] - 2026-08-28

### Added
- **Atlas Copco logo** bundled at `assets/atlas_copco_logo.png`
  (889×281 px, RGBA, transparent background). The same file is used
  across **every visible surface** of the dashboard so the branding
  looks consistent in all appearances:
    * **Browser tab / favicon** — set via `st.set_page_config(page_icon=…)`.
    * **Sidebar header** — full-width `st.image(...)` at the top of the
      sidebar so the logo is visible while navigating tabs.
    * **Main page header** — placed in a 1:6 column layout alongside
      the title so it sits in the upper-left of the main content area.
    * **README.md** — `<img src="assets/atlas_copco_logo.png" …>` at the
      top of the file, centered, 360 px wide.
    * **PyInstaller bundle** — `build_windows.bat` now passes
      `--add-data "assets;assets"` so the logo is packed inside the
      standalone `.exe` and resolves correctly at runtime.

### Changed
- `app/paths.py` — new `ASSETS_DIR` and `LOGO_FILE` constants
  pointing at the project-rooted `assets/` folder.
- `app/streamlit_app.py` — imports `LOGO_FILE` and uses it for the
  favicon, the sidebar image, and the main-header logo column.
  Falls back silently to the existing `🔧` page-icon emoji if the
  asset is missing (e.g. running tests without the bundled logo).
- `build_windows.bat` — exe renamed `OpenProtocolDashboard` →
  `ToolCRUDDashboard`; new `--add-data "assets;assets"` line.
- `README.md` — logo image added above the H1; version badge
  bumped 1.2.1 → 1.2.2.
- `__version__` bumped `1.2.1` → `1.2.2` (PATCH per SemVer:
  visual/UI asset addition, no behaviour change).

### Notes
- The logo asset is a 887×281 RGBA PNG that came from a
  `removebg`-processed source — transparent background verified.
- If the asset is ever moved or renamed, only `app/paths.py`'s
  `LOGO_FILE` constant needs updating; the rest of the code picks
  it up via the import.


## [1.2.1] - 2026-08-28

### Changed
- **Product renamed** from "Open Protocol CRUD Dashboard" to
  **"Tool CRUD Dashboard"**. Updated everywhere the product name
  appears:
    * `app/__init__.py` — module docstring + `version_string()`.
    * `app/streamlit_app.py` — module docstring + `st.set_page_config`
      `page_title` + `st.title()` heading.
    * `run.py` — module docstring + startup banner.
    * `build_windows.bat` — header comment.
    * `README.md` — H1 + run.py log example + Versioning section
      source-of-truth reference + Project Layout.
- `__version__` bumped `1.2.0` → `1.2.1` (PATCH per SemVer:
  copy/wording change, no behaviour change).

### Notes
- References to **"Open Protocol"** that mean the wire protocol
  (Atlas Copco Open Protocol, MIDs, frame parsing, controller pull,
  etc.) are intentionally left untouched — those describe the
  protocol, not the product name.
- CHANGELOG history (v1.0.0 → v1.2.0) keeps the old product name
  inside its release notes — the changelog is an immutable record.


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
