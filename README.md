<div align="center">

# 🔧 Open Protocol CRUD Dashboard

### A cross-platform Streamlit app that talks to tightening controllers over **Atlas Copco Open Protocol**

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Pandas](https://img.shields.io/badge/Pandas-2.0%2B-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![License](https://img.shields.io/badge/License-Internal%20Use-yellow?style=for-the-badge)](#-license)
[![Version](https://img.shields.io/badge/Version-1.0.0-success?style=for-the-badge)](#-versioning)

[![Platforms](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](#-cross-platform-launcher)
[![Platforms](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](#-cross-platform-launcher)
[![Platforms](https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white)](#-cross-platform-launcher)
[![Platforms](https://img.shields.io/badge/WSL-0C3F70?style=for-the-badge&logo=ubuntu&logoColor=white)](#-cross-platform-launcher)

</div>

---

<div align="center">

```
┌──────────────────────────────────────────────────────────────────────┐
│  🔌 TCP Socket                                                       │
│       │                                                              │
│       ▼                                                              │
│  🛠  Atlas Copco Controller  ←→  Open Protocol (MID 0040, 0060, ...) │
│       │                                                              │
│       ▼                                                              │
│  🐍  Python Client (length-aware, NUL-tolerant)                      │
│       │                                                              │
│       ▼                                                              │
│  🗄  SQLAlchemy ORM  →  SQLite (default) · PostgreSQL · MySQL · MSSQL │
│       │                                                              │
│       ▼                                                              │
│  📊  Streamlit UI  ·  Live · CRUD · KPIs · Search                    │
└──────────────────────────────────────────────────────────────────────┘
```

</div>

---

## 📑 Table of Contents

- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [🏗️ Architecture](#%EF%B8%8F-architecture)
- [📊 UI Tour](#-ui-tour)
- [🗄️ Database](#%EF%B8%8F-database)
- [🌐 Remote DB](#-remote-db)
- [🪟 Cross-Platform Launcher](#-cross-platform-launcher)
- [📦 Windows Packaging](#-windows-packaging)
- [🧰 Known Quirks](#-known-quirks)
- [🚦 Troubleshooting](#-troubleshooting)
- [🔢 Versioning](#-versioning)
- [📋 Project Layout](#-project-layout)
- [🤝 Contributing](#-contributing)
- [⚖️ License](#%EF%B8%8F-license)

---

## ✨ Features

<div align="center">

| 🌐 **Live Data** | 📝 **CRUD** | 📊 **KPIs** | 🔍 **Search** |
|:---:|:---:|:---:|:---:|
| Open Protocol MIDs 0040 / 0060 / 0080 / 0010 / 0030 | Create / Read / Update / Delete maintenance log rows | Real-time metrics & charts | Filter the log, export CSV |
| Fresh socket per click | Same schema as the XLSX + all Open Protocol fields | Daily / monthly trends | One-click CSV export |
| NUL-tolerant, length-aware | Natural-key dedup | Calibration-overdue alerts | Filter by executor, tool, date |

</div>

<table>
<tr>
<td>🔌 <b>Open Protocol</b></td>
<td>Atlas Copco native protocol over raw TCP (port 4545). Reads multi-segment responses using the 4-digit ASCII length field. Tolerates the leading <code>\x00</code> separator that <code>ScaniaProtocolAdapter</code> prepends to every frame.</td>
</tr>
<tr>
<td>� <b>SQLAlchemy ORM</b></td>
<td>One model — <code>MaintenanceLog</code> — that merges the XLSX work-order columns (Dutch: <i>UITVOERDER</i>, <i>AFWERING STATUS</i>, <i>ORDER SAP</i>, <i>STATUS OPTIES SAP</i>, <i>DATUM</i>, <i>BEGIN</i>, <i>EIND</i>) with every Open Protocol field. Default backend is SQLite, swap to PostgreSQL/MySQL/MSSQL via <code>DATABASE_URL</code>.</td>
</tr>
<tr>
<td>📊 <b>KPI Dashboard</b></td>
<td>Records · total tightenings · OK-rate · avg torque · daily/monthly trends · top executors · top tools · status distribution · calibration overdue alerts.</td>
</tr>
<tr>
<td>🔍 <b>Search + CSV</b></td>
<td>Filter by executor, status, SAP order, tool serial, date range, tightening status. One-click CSV export.</td>
</tr>
<tr>
<td>🌍 <b>Cross-platform launcher</b></td>
<td>One <code>run.py</code> works on Windows / WSL / Linux / macOS. Detects OS, locates Python 3.10+, creates a venv, installs deps, opens the browser.</td>
</tr>
<tr>
<td>📦 <b>Windows packaging</b></td>
<td><code>build_windows.bat</code> ships a single-file <code>OpenProtocolDashboard.exe</code> via PyInstaller. No Python install required on the target PC.</td>
</tr>
<tr>
<td>🔢 <b>Versioning</b></td>
<td>Semantic Versioning 2.0 in <code>app/__version__</code>. Surfaced in the sidebar, printed by <code>run.py --version</code>, documented in <code>CHANGELOG.md</code>.</td>
</tr>
</table>

---

## 🚀 Quick Start

### Prerequisites

- 🐍 **Python 3.10 or newer** (3.11 / 3.12 / 3.13 all work)
- 🌐 **Network reachability** to the controller (same VLAN, port 4545 open)
- 💾 **~150 MB** free disk space for the venv + dependencies

### Run

The launcher does everything. Open a terminal in the project folder:

#### 🪟 Windows

```bat
python run.py
```

#### 🐧 Linux / WSL / 🍎 macOS

```bash
python3 run.py
```

The launcher will:

1. 🖨 Print the version banner and detected platform
2. 🔍 Locate a Python 3.10+ interpreter
3. � Create `.venv/` in the project folder
4. 📥 `pip install -r requirements.txt` (streamlit, pandas, sqlalchemy)
5. 🚀 Launch Streamlit on `http://localhost:8501` and open a browser tab

<div align="center">

```
[run] Open Protocol CRUD Dashboard v1.0.0
[run] Platform: wsl (Linux 5.15.0-ubuntu)
[run] Using Python: /usr/bin/python3
[run] Launching: /home/user/.venv/bin/python -m streamlit run app/streamlit_app.py ...
```

</div>

### Useful flags

```bash
python run.py --port 9000                        # change port
python run.py --host 127.0.0.1                   # bind localhost only (no LAN access)
python run.py --no-browser                       # do not auto-open browser
python run.py --recreate-venv                    # nuke .venv and rebuild
python run.py --db postgresql://user:pw@host/db  # use a remote DB
python run.py --version                          # print version and exit
```

---

## 🏗️ Architecture

<div align="center">

```
                    ┌────────────────────────────┐
                    │   Controller (192.168.x.x) │
                    │   Atlas Copco Open Protocol│
                    │   Port 4545 / TCP          │
                    └─────────────┬──────────────┘
                                  │ MIDs
                                  │ 0001 / 0040 / 0060 /
                                  │ 0080 / 0010 / 0030
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │  app/protocol.py           │
                    │  · _recv_exact()           │  length-aware TCP read
                    │  · _recv_oped()            │  NUL-prefix tolerant
                    │  · parse_mid_*()           │  byte-offset parsers
                    └─────────────┬──────────────�
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │  app/crud.py               │
                    │  · create_log()            │  INSERT ... ON CONFLICT
                    │  · search_logs()           │  filter & paginate
                    │  · update_log() / delete() │
                    └─────────────┬──────────────┘
                                  │ SQLAlchemy
                                  ▼
                    ┌────────────────────────────┐
                    │  app/db.py                 │
                    │  · get_engine()            │  reads DATABASE_URL
                    │  · session_scope()         │  commits/rolls back
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │  Database                  │
                    │  SQLite (default)          │
                    │  PostgreSQL / MySQL / MSSQL│
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │  app/streamlit_app.py      │
                    │  ┌──────────────────────┐  │
                    │  │ Live │ CRUD │ KPIs │ Search │
                    │  └──────────────────────┘  │
                    └────────────────────────────┘
                                  │
                                  ▼
                            🌐 Browser
```

</div>

---

## 📊 UI Tour

After launch, the dashboard opens on the **🟢 Live data** tab.

### 🟢 Live data

Enter controller IP + port, then click any of the three buttons:

| Button | What it does |
|---|---|
| 🛠 **Get tool data** | Fetches MID 0040 (tool data) + MID 0080 (protocol version). Auto-saves as a new log row. |
| � **Get controller info** | Fetches MIDs 0080, 0010, 0030 (protocol version, parameter set IDs, job list). |
| 🔩 **Get last tightening** | Fetches MID 0060 (last tightening result) with torque / angle / status. |

The result is auto-saved as a new log row, or flagged as a duplicate (🔁 toast) if the natural key already exists.

### 📝 CRUD

- **Create** — full form with every XLSX field + optional Open Protocol fields.
- **Update** — pick any row, edit executor / status / SAP order / date / times / notes.
- **Delete** — multi-select with safety checkbox.

### 📊 KPIs

```
┌──────────┬──────────┬──────────┬──────────┐
│ Records  │Tightenings│  OK rate │Avg torque│
│   123    │   5,678   │  98.4 %  │ 12.34 Nm │
└──────────┴──────────┴──────────┴──────────┘
```

- 📈 **Daily activity** (line chart, last 30 days, backfilled)
- 📊 **Monthly activity** (bar chart, last 12 months, backfilled)
- 🏆 **Top executors** (per-technician count)
- � **Top tools** (per-tool count)
- 📋 **Status distribution** (Afgewerkt / In uitvoering / …)
- ⚠️ **Calibration overdue alerts** (tools older than 12 months)

### 🔍 Search

Filter the log table by any combination of fields. Results render in a dataframe; one-click CSV export.

### 📋 Sidebar

- 🔢 Version banner
- 🌐 Platform
- 🗄️ Active DB URL
- 🧮 Live counters (records, OK rate, average torque, last entry timestamp)
- 🔄 Reload KPIs button

---

## 🗄️ Database

One table: **`maintenance_log`**.

### Natural-key uniqueness rule

```sql
UNIQUE INDEX uq_log_natural_key ON (
    sap_order, work_date, tool_serial, tightening_id
)
```

A re-fetch of identical data is silently skipped — no duplicate rows, no exception.

### Full schema

```sql
CREATE TABLE maintenance_log (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at                DATETIME NOT NULL,
    updated_at                DATETIME NOT NULL,
    source                    VARCHAR(16) DEFAULT 'manual',  -- 'manual' / 'controller'
    notes                     TEXT,

    -- XLSX-derived work-order columns (Dutch labels)
    executor                  VARCHAR(64),   -- UITVOERDER
    status                    VARCHAR(32),   -- AFWERING STATUS
    sap_order                 VARCHAR(32),   -- ORDER SAP
    sap_status_options        VARCHAR(64),   -- STATUS OPTIES SAP
    work_date                 DATE,          -- DATUM
    start_time                VARCHAR(8),    -- BEGIN  (HH:MM:SS)
    end_time                  VARCHAR(8),    -- EIND   (HH:MM:SS)

    -- Open Protocol MID 0040
    tool_serial               VARCHAR(32),
    controller_serial         VARCHAR(32),
    total_tightenings         INTEGER,
    tightenings_since_svc     INTEGER,
    last_calibration_date     VARCHAR(16),
    last_service_date         VARCHAR(16),
    calibration_value         VARCHAR(16),
    firmware                  VARCHAR(32),

    -- Open Protocol MID 0060 (last tightening result)
    tightening_id             VARCHAR(32),
    tightening_status         VARCHAR(16),   -- OK / NOK / Aborted
    torque_status             VARCHAR(16),
    angle_status              VARCHAR(16),
    torque_value              FLOAT,
    torque_min                FLOAT,
    torque_target             FLOAT,
    torque_max                FLOAT,
    angle_value               FLOAT,
    angle_min                 FLOAT,
    angle_target              FLOAT,
    angle_max                 FLOAT,
    cell_id                   VARCHAR(16),
    job_number                VARCHAR(16),
    batch_status              VARCHAR(8),
    batch_counter             INTEGER,
    tightening_time           VARCHAR(32),

    -- Open Protocol MID 0080 (controller / adapter)
    protocol_version          VARCHAR(16),
    controller_ip             VARCHAR(45),
    controller_port           INTEGER,

    -- Debug
    raw_response              TEXT
);
```

---

## 🌐 Remote DB

Local SQLite is the default. To point at a remote server, set `DATABASE_URL` (or pass `--db`). The matching driver must be added to `requirements.txt` first; the default file ships with the common ones commented out:

### 🐘 PostgreSQL (most common for production)

```bash
pip install "psycopg[binary]>=3.1"
DATABASE_URL=postgresql://op_user:secret@db-host:5432/op_protocol python run.py
```

### 🐬 MySQL / MariaDB

```bash
pip install pymysql
DATABASE_URL=mysql+pymysql://op_user:secret@db-host:3306/op_protocol python run.py
```

### � Microsoft SQL Server

```bash
pip install pyodbc
DATABASE_URL="mssql+pyodbc://op_user:secret@db-host/op_protocol?driver=ODBC+Driver+17+for+SQL+Server" python run.py
```

The launcher passes `DATABASE_URL` straight through to the app; the schema is created automatically on first connect.

The dashboard sidebar shows the active `DATABASE_URL` and platform so you can confirm at a glance.

---

## 🪟 Cross-Platform Launcher

The launcher (`run.py`) auto-detects your OS, finds a compatible Python, builds a venv, and installs dependencies — all from a single file. It works identically on:

| OS | Python detection path |
|---|---|
| 🪟 **Windows** | `python` on PATH, then `C:\Python313\python.exe`, `C:\Python312\python.exe`, …, `%LOCALAPPDATA%\Programs\Python\Python313\python.exe` |
| � **Linux** | `python3` on PATH, then `/usr/bin/python3`, `/usr/local/bin/python3`, `/usr/bin/python3.13`, … |
| �🐧 **WSL** | Same as Linux, plus the launcher detects `/proc/version` containing `microsoft` / `wsl` and labels the platform accordingly. |
| 🍎 **macOS** | `python3` on PATH, then `/opt/homebrew/bin/python3`, `/usr/bin/python3.13`, … |

### 🔍 OS detection

```python
def detect_platform() -> str:
    """Return one of: 'windows', 'wsl', 'linux', 'macos'."""
    s = sys.platform
    if s.startswith("win"):
        return "windows"
    if s == "linux":
        try:
            with open("/proc/version") as f:
                if "microsoft" in f.read().lower() or "wsl" in f.read().lower():
                    return "wsl"
        except OSError:
            pass
        return "linux"
    if s == "darwin":
        return "macos"
```

The platform string is passed into the app via the `OPEN_PROTOCOL_PLATFORM` env var so the Streamlit sidebar can show it.

### 📁 Virtualenv lifecycle

```
�─ run.py ──────────────────────────────────────────────────┐
│  1. Detect platform                                        │
│  2. Find Python ≥ 3.10                                     │
│  3. if not .venv/: create via stdlib venv.EnvBuilder       │
│  4. if not streamlit installed: pip install -r requirements│
│  5. Set DATABASE_URL / OPEN_PROTOCOL_PLATFORM env vars     │
│  6. Spawn streamlit run app/streamlit_app.py ...            │
│  7. After 2 s delay, open browser to http://localhost:PORT │
└────────────────────────────────────────────────────────────┘
```

### 📋 Thin wrappers

`start.sh` (Linux/WSL/macOS) and `start.bat` (Windows) are 4-line wrappers that just forward to `run.py`. They exist for muscle-memory compatibility.

---

## 📦 Windows Packaging

Build on Windows (or WSL with a Windows Python). Output is platform-specific.

```bat
build_windows.bat
REM -> dist\OpenProtocolDashboard.exe
```

The bundle contains Python + Streamlit + Pandas + SQLAlchemy + every declared dependency. **~150 MB**.

<div align="center">

| Stage | Action |
|---|---|
| 1️⃣ | `python -m venv .venv` (only if missing) |
| 2️⃣ | `pip install -r requirements.txt` |
| 3️⃣ | `pip install pyinstaller` |
| 4️⃣ | `pyinstaller --onefile --windowed --name OpenProtocolDashboard --add-data "app;app" --collect-all streamlit --collect-all sqlalchemy --collect-all pandas run.py` |
| 5️⃣ | `dist\OpenProtocolDashboard.exe` ready |

</div>

Antivirus false positives on PyInstaller binaries are common; sign with `signtool` before shipping to shop-floor PCs.

---

## 🧰 Known Quirks

<table>
<tr>
<th>Quirk</th>
<th>Where handled</th>
</tr>
<tr>
<td>🟢 NUL byte prefix on every Open Protocol frame (ScaniaProtocolAdapter)</td>
<td><code>app/protocol.py::_recv_oped</code> skips leading <code>\x00</code> bytes before parsing the length field</td>
</tr>
<tr>
<td>🟢 Multi-segment TCP responses</td>
<td><code>app/protocol.py::_recv_exact</code> reads exactly the declared number of bytes</td>
</tr>
<tr>
<td>🟡 MID 0040 byte offsets vary by firmware revision</td>
<td>Parsers return empty strings (not crashes) for short responses; open the <b>Raw MID 0040</b> expander to verify</td>
</tr>
<tr>
<td>🟡 MID 0060 offset 137 = firmware in some revisions</td>
<td>Parser returns <code>firmware=''</code> for short responses — non-fatal</td>
</tr>
<tr>
<td>🟢 PEP 668 <code>externally-managed-environment</code> on Debian/Ubuntu</td>
<td>Launcher always creates a venv first; system pip never touched</td>
</tr>
</table>

---

## 🚦 Troubleshooting

<div align="center">

| 🚨 Symptom | 🔍 Likely cause | 🔧 Fix |
|---|---|---|
| `Network error: timed out` | PC cannot reach the controller | Same VLAN, no firewall block on port 4545. Try `nc -vz <controller-ip> 4545` |
| `Invalid Open Protocol length header` | Adapter prepends unexpected bytes | Open the **Raw MID xxxx** expander and report the bytes |
| `BlockingIOError [Errno 26]` | Old version, reused global socket | Pull latest `app/protocol.py` |
| `externally-managed-environment` on `pip install` | PEP 668 (Debian/Ubuntu) | Use `python run.py` — it creates a venv automatically |
| `sqlalchemy.exc.OperationalError` on remote DB | Wrong host/port/creds/missing driver | Re-check `DATABASE_URL`; ensure the matching driver is installed |
| Port 8501 already in use | Another Streamlit instance running | `python run.py --port 9000` (or close the old one) |

</div>

---

## 🔢 Versioning

Semantic Versioning 2.0. The single source of truth is `app/__init__.py::__version__ = "1.0.0"`. It is read by:

- the Streamlit sidebar
- `run.py --version`
- `CHANGELOG.md` (must be updated together with `__version__`)

When bumping:

1. Update `__version__`.
2. Add a new entry at the top of `CHANGELOG.md`.
3. Commit both files together.
4. `git tag v<__version__>`.

<div align="center">

| Bump | When |
|---|---|
| 🔴 **MAJOR** | Breaking schema change, UI rewrite, or removed MIDs |
| 🟡 **MINOR** | New feature (new MID, new KPI, new tab) — backward-compatible |
| 🟢 **PATCH** | Bug fix, copy/wording, dependency bump |

</div>

---

## 📋 Project Layout

```
open-protocol-dashboard/
├── 🐍 app/                          Python package
│   ├── __init__.py                  __version__ = '1.0.0'
│   ├── paths.py                     BASE_DIR, PLATFORM, get_database_url
│   ├── protocol.py                  Atlas Copco Open Protocol client
│   ├── models.py                    SQLAlchemy ORM (MaintenanceLog)
│   ├── db.py                        Engine + session_scope
│   ├── crud.py                      Create / Read / Update / Delete
│   ├── kpis.py                      KPI computations
│   └── streamlit_app.py             Streamlit UI (506 lines)
├── 📂 docs/                         Project artefacts (PDFs, diagrams)
├── 🚀 run.py                        Cross-platform launcher (265 lines)
├── 🐧 start.sh                      Linux / WSL / macOS wrapper
├── � start.bat                     Windows wrapper
├── 📦 build_windows.bat             PyInstaller → OpenProtocolDashboard.exe
├── 🚀 launcher.py                   Standalone Streamlit wrapper (legacy)
├── 📋 requirements.txt              streamlit, pandas, sqlalchemy
├── 🔐 .env.example                  DATABASE_URL samples
├── 🙈 .gitignore
├── 📖 README.md                     (this file)
└── 📜 CHANGELOG.md                  Versioned change log
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-new-tab`)
3. Make your change, bump `app/__version__` per [the version policy](#-versioning), update `CHANGELOG.md`
4. Commit (`git commit -m "feat: add multi-spindle MID 0210"`)
5. Push (`git push origin feat/my-new-tab`)
6. Open a Pull Request

---

## ⚖️ License

**Internal use only.** This project is shared publicly for visibility, not for redistribution. See the [CHANGELOG.md](CHANGELOG.md) for the project history and [requirements.txt](requirements.txt) for the dependency licenses.

---

<div align="center">

Made with ❤️ for the shop floor.

🛠 **Atlas Copco** · 🐍 **Python** · 📊 **Streamlit** · � **SQLAlchemy**

</div>
