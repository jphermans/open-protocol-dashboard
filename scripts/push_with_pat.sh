#!/usr/bin/env bash
# scripts/push_with_pat.sh
# ---------------------------------------------------------------------------
# Push the current branch and tag to GitHub using a PAT stored in `.env`.
#
# Why this exists:
#   - GitHub PATs are sensitive. Pasting them in chat logs them. Hard-coding
#     them in scripts is a leak. Storing them in shell history is a leak.
#   - This wrapper reads `GITHUB_TOKEN` from the gitignored `.env` file,
#     uses it in env-var-only mode for exactly one push, then wipes it.
#
# Usage:
#   ./scripts/push_with_pat.sh                       # push current branch + tag matching __version__
#   ./scripts/push_with_pat.sh main                  # push 'main' + tag matching __version__
#   ./scripts/push_with_pat.sh feature/x v0.5.1      # custom branch + custom tag
#
# Prerequisites:
#   - .env at the project root containing:   GITHUB_TOKEN=ghp_…
#   - You must be inside the repo root, with a clean working tree.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"

# Tag defaults to the current app __version__ if not provided
if [[ $# -ge 2 ]]; then
  TAG="$2"
else
  TAG="v$(python3 -c 'from app import __version__; print(__version__)' 2>/dev/null || echo '')"
fi

# --- safety: load token from .env (gitignored) -----------------------------
if [[ ! -f .env ]]; then
  echo "error: .env not found. Create it with:   echo 'GITHUB_TOKEN=ghp_…' >> .env" >&2
  exit 2
fi
GITHUB_TOKEN="$(grep -E '^GITHUB_TOKEN=' .env | head -1 | cut -d= -f2-)"
if [[ -z "$GITHUB_TOKEN" || "$GITHUB_TOKEN" == "<your_pat>" ]]; then
  echo "error: GITHUB_TOKEN missing or unset in .env" >&2
  exit 3
fi

# --- safety: kill history before doing anything with the token -------------
set +o history
unset HISTFILE

# --- resolve login via API (PAT in Authorization header, never on argv) ----
LOGIN="$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user         | python3 -c 'import sys,json; print(json.load(sys.stdin).get("login",""))')"
if [[ -z "$LOGIN" ]]; then
  echo "error: token does not resolve to a GitHub login (revoked? wrong scope?)" >&2
  unset GITHUB_TOKEN
  exit 4
fi

# --- save the SSH remote URL (we restore it at the end) ---------------------
SSH_URL="$(git remote get-url origin)"

# --- one Python pass: switch remote, push, restore, verify, wipe -----------
# Export everything Python will read from os.environ inside the heredoc.
# (The inner "$VAR" placeholders are expanded by bash; exporting makes
# os.environ[...] lookups in Python work as well, so both styles are safe.)
export PUSH_PAT="$GITHUB_TOKEN"
export SSH_URL LOGIN BRANCH TAG
python3 <<PYEOF
import os, subprocess, sys
pat  = os.environ['PUSH_PAT']
ssh  = os.environ['SSH_URL']
login = os.environ['LOGIN']
branch = os.environ['BRANCH']
tag    = os.environ.get('TAG', '') or None
env = os.environ.copy()
env['PUSH_PAT'] = pat

def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

# 1. switch remote to HTTPS+token
sh(['git','remote','set-url','origin',
    f'https://x-access-token:{pat}@github.com/{login}/open-protocol-dashboard.git'])

# 2. push branch
rc, _, err = sh(['git','push','origin', f'{branch}:{branch}'])
if rc != 0:
    sh(['git','remote','set-url','origin', ssh])
    print(f'push branch failed: {err}', file=sys.stderr); sys.exit(5)
print(f'branch {branch} pushed')

# 3. push tag (only if requested)
if tag:
    rc, _, err = sh(['git','push','origin', tag])
    if rc != 0:
        sh(['git','remote','set-url','origin', ssh])
        print(f'push tag failed: {err}', file=sys.stderr); sys.exit(6)
    print(f'tag {tag} pushed')

# 4. verify remote == local
_, rh, _ = sh(['git','ls-remote','origin','HEAD'])
_, lh, _ = sh(['git','rev-parse','HEAD'])
print(f'remote HEAD: {rh}')
print(f'local  HEAD: {lh}')
print(f'match: {rh.split()[0] == lh}')

# 5. restore SSH
sh(['git','remote','set-url','origin', ssh])
PYEOF

# --- final wipe ------------------------------------------------------------
unset GITHUB_TOKEN PUSH_PAT SSH_URL LOGIN
history -c 2>/dev/null || true
: > "$HOME/.bash_history" 2>/dev/null || true
echo "PAT wiped, bash history cleared, remote URL restored to SSH."
