#!/usr/bin/env python3
"""Cross-platform launcher for the Open Protocol CRUD dashboard.

Works identically on Windows, Linux, macOS, and WSL. Single-file replacement
for the previous start.sh + start.bat pair.

What it does:
  1. Detect platform (Windows vs Linux/macOS; flags WSL specifically).
  2. Locate Python 3.10+ on PATH (or in common install locations).
  3. Create a project-local virtualenv on first run.
  4. Install / upgrade dependencies from requirements.txt.
  5. Launch Streamlit, opening the browser automatically.

Usage:
    python run.py            # launch the dashboard
    python run.py --port 9000  # launch on a different port
    python run.py --no-browser  # do not open a browser tab automatically
    python run.py --db postgresql://user:pw@host/db   # override DB at runtime
    python run.py --recreate-venv  # nuke .venv and rebuild
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import venv
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR    = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
MIN_PY_MAJOR = 3
MIN_PY_MINOR = 10


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
def detect_platform() -> str:
    """Return one of: 'windows', 'wsl', 'linux', 'macos'."""
    s = sys.platform
    if s.startswith("win"):
        return "windows"
    if s == "linux":
        try:
            with open("/proc/version", "r", encoding="utf-8") as f:
                txt = f.read().lower()
            if "microsoft" in txt or "wsl" in txt:
                return "wsl"
        except OSError:
            pass
        return "linux"
    if s == "darwin":
        return "macos"
    return s or "unknown"


def is_wsl() -> bool:
    return detect_platform() == "wsl"


# ---------------------------------------------------------------------------
# Python discovery
# ---------------------------------------------------------------------------
def _candidate_python_paths() -> list[Path]:
    """Look in common locations for a usable Python interpreter."""
    candidates: list[Path] = []
    if sys.platform.startswith("win"):
        candidates += [
            Path(sysconfig.get_config_var("BINDIR") or "") / "python.exe",
            Path("C:/Python313/python.exe"),
            Path("C:/Python312/python.exe"),
            Path("C:/Python311/python.exe"),
            Path("C:/Python310/python.exe"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python313/python.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python312/python.exe",
        ]
    else:
        candidates += [
            Path("/usr/bin/python3"),
            Path("/usr/local/bin/python3"),
            Path("/opt/homebrew/bin/python3"),
            Path("/usr/bin/python3.13"),
            Path("/usr/bin/python3.12"),
            Path("/usr/bin/python3.11"),
            Path("/usr/bin/python3.10"),
        ]
    return [p for p in candidates if p and p.exists()]


def find_python() -> str:
    """Return the path to a usable Python >= MIN_PY version. Die if none."""
    for label in (sys.executable, "python3", "python"):
        path = shutil.which(label) if not Path(label).is_file() else label
        if not path:
            continue
        if _python_version_ok(path):
            return path
    for cand in _candidate_python_paths():
        if _python_version_ok(str(cand)):
            return str(cand)
    die(
        f"Python >= {MIN_PY_MAJOR}.{MIN_PY_MINOR} is required but was not found.\n"
        "Install Python from https://www.python.org/downloads/ and retry."
    )


def _python_version_ok(path: str) -> bool:
    try:
        out = subprocess.check_output(
            [path, "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    try:
        major, minor = (int(x) for x in out.split())
    except ValueError:
        return False
    return (major, minor) >= (MIN_PY_MAJOR, MIN_PY_MINOR)


# ---------------------------------------------------------------------------
# Virtualenv lifecycle
# ---------------------------------------------------------------------------
def venv_python(venv_dir: Path) -> Path:
    if sys.platform.startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_pip(venv_dir: Path) -> list[str]:
    return [str(venv_python(venv_dir)), "-m", "pip"]


def create_venv(venv_dir: Path) -> None:
    print(f"[run] Creating virtualenv at {venv_dir} ...")
    builder = venv.EnvBuilder(
        system_site_packages=False,
        clear=True,
        symlinks=(not sys.platform.startswith("win")),
        with_pip=True,
    )
    builder.create(str(venv_dir))


def install_requirements(venv_dir: Path) -> None:
    if not REQUIREMENTS.exists():
        die(f"Missing {REQUIREMENTS}")
    print(f"[run] Installing requirements from {REQUIREMENTS.name} ...")
    subprocess.check_call(
        venv_pip(venv_dir) + ["install", "--upgrade", "pip"],
        stdout=subprocess.DEVNULL,
    )
    subprocess.check_call(
        venv_pip(venv_dir) + ["install", "-r", str(REQUIREMENTS)]
    )


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------
def die(msg: str, code: int = 1) -> None:
    print(f"[run] FATAL: {msg}", file=sys.stderr)
    sys.exit(code)


def streamlit_is_installed(venv_dir: Path) -> bool:
    try:
        subprocess.check_call(
            [str(venv_python(venv_dir)), "-c", "import streamlit"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="8501")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not auto-open a browser tab")
    parser.add_argument("--db", default=None,
                        help="Override DATABASE_URL env var, e.g. "
                             "postgresql://user:pw@host:5432/db")
    parser.add_argument("--recreate-venv", action="store_true",
                        help="Delete .venv and rebuild it before installing deps")
    parser.add_argument("--version", action="store_true",
                        help="Print the dashboard version and exit")
    args = parser.parse_args(argv)

    if args.version:
        # Lazy import: the app package only matters when launching Streamlit.
        from app import version_string
        print(version_string())
        return 0

    plat = detect_platform()
    # Read the version directly from the package so it never drifts from
    # the one shown in the Streamlit sidebar.
    try:
        from app import version_string as _vs
        print(f"[run] {_vs()}")
    except Exception:
        pass
    print(f"[run] Platform: {plat} ({platform.platform(terse=True)})")

    py = find_python()
    print(f"[run] Using Python: {py}")

    if args.recreate_venv and VENV_DIR.exists():
        print(f"[run] Removing {VENV_DIR} ...")
        shutil.rmtree(VENV_DIR)

    if not VENV_DIR.exists() or not venv_python(VENV_DIR).exists():
        create_venv(VENV_DIR)

    if not streamlit_is_installed(VENV_DIR):
        install_requirements(VENV_DIR)

    env = os.environ.copy()
    if args.db:
        env["DATABASE_URL"] = args.db
    env["OPEN_PROTOCOL_PLATFORM"] = plat
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        str(venv_python(VENV_DIR)), "-m", "streamlit", "run",
        "app/streamlit_app.py",
        "--server.port", str(args.port),
        "--server.address", str(args.host),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    if args.no_browser:
        cmd += ["--browser.serverAddress", "localhost"]

    print(f"[run] Launching: {' '.join(cmd)}")
    if not args.no_browser:
        # Open the browser after a short delay (fire-and-forget).
        import threading, time, webbrowser
        def _open_browser() -> None:
            time.sleep(2.0)
            webbrowser.open(f"http://localhost:{args.port}")
        threading.Thread(target=_open_browser, daemon=True).start()

    try:
        return subprocess.call(cmd, env=env, cwd=str(PROJECT_DIR))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
