#!/usr/bin/env bash
# Linux / WSL / macOS launcher.
# Equivalent to:  python run.py
# Use this when you want the old single-shot script behaviour.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 run.py "$@"
