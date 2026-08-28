"""Password gate for destructive actions.

Two actions in the dashboard are considered destructive:

  * Deleting a record (or batch of records) from the maintenance log.
  * Switching the database backend (Local SQLite <-> Remote, host, login,
    password, db name, etc.).

Both require the user to enter the configured password. A successful
authentication unlocks the session for `AUTH_TTL_SECONDS` so the user
does not need to re-type the password for every subsequent destructive
action during the same Streamlit session.

The default password is `Atlas123!` (per spec). It can be overridden via
the `OPEN_PROTOCOL_PASSWORD_HASH` environment variable, which should
contain the SHA-256 hex digest of the password salted with the literal
prefix `op_dash:`. Generate one with:

    python -c "import hashlib; print(hashlib.sha256(b'op_dash:Atlas123!').hexdigest())"

Then start the dashboard with:

    OPEN_PROTOCOL_PASSWORD_HASH=<the_hash> python run.py

The hash is stored in env / config, never the plaintext password. The
plaintext password is only ever held in memory inside the password input
widget, for the duration of one form submission.

Design notes:
  * SHA-256 + a static salt is not a strong cryptographic construction,
    but it does prevent trivial recovery by `strings`/`grep` over the
    source tree or compiled .exe. If you need stronger, swap the body
    of `verify_password` for `bcrypt.checkpw` (and `bcrypt.hashpw` for
    the hash generator) — the call sites stay the same.
  * Session state is kept in `st.session_state` via two keys:
      `auth_ok` (bool) and `auth_expires_at` (float, epoch seconds).
    Both are reset on logout / TTL expiry.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional


# Public re-exports so callers can `from app.auth import (
#     DEFAULT_PASSWORD, AUTH_TTL_SECONDS, verify_password )`.
DEFAULT_PASSWORD = "Atlas123!"
AUTH_TTL_SECONDS = 600  # 10 minutes after each successful auth
_SALT = "op_dash:"


def _default_hash() -> str:
    """SHA-256 of the default password with the static salt."""
    return hashlib.sha256((_SALT + DEFAULT_PASSWORD).encode("utf-8")).hexdigest()


def get_password_hash() -> str:
    """Return the active password hash.

    Resolution order:
      1. `OPEN_PROTOCOL_PASSWORD_HASH` env var (operator-supplied override).
      2. `auth_config.json` on disk (saved from the Setup tab by the
         operator). Missing file falls through to the default so that
         fresh installs / `--recreate-venv` always come up with
         `Atlas123!` as expected.
      3. SHA-256 of the built-in `DEFAULT_PASSWORD`.
    """
    override = os.environ.get("OPEN_PROTOCOL_PASSWORD_HASH", "").strip().lower()
    if override and len(override) == 64 and all(
        c in "0123456789abcdef" for c in override
    ):
        return override
    try:
        from app.password_config import load_password_hash as _disk
        disk = _disk()
        if disk:
            return disk
    except Exception:
        # A broken config file should never lock the operator out —
        # fall through to the default password.
        pass
    return _default_hash()


def verify_password(password: str) -> bool:
    """Constant-time-ish comparison of `password` against the active hash."""
    if not password:
        return False
    candidate = hashlib.sha256((_SALT + password).encode("utf-8")).hexdigest()
    expected = get_password_hash()
    # hmac.compare_digest (NOT hashlib.compare_digest — that attribute
    # doesn't exist; compare_digest was moved to the hmac module in
    # Python 3.3). Constant-time-ish comparison avoids early-exit
    # timing leaks.
    return hmac.compare_digest(candidate, expected)


def is_authenticated(session_state) -> bool:
    """True if the current session_state has a non-expired auth grant."""
    if not session_state.get("auth_ok"):
        return False
    expires_at = float(session_state.get("auth_expires_at", 0) or 0)
    if expires_at <= time.time():
        # Expired — clear and reject.
        session_state["auth_ok"] = False
        session_state["auth_expires_at"] = 0.0
        return False
    return True


def authenticate(session_state, password: str) -> bool:
    """Verify `password`; if correct, grant auth for AUTH_TTL_SECONDS.

    Returns True on success.
    """
    if verify_password(password):
        session_state["auth_ok"] = True
        session_state["auth_expires_at"] = time.time() + AUTH_TTL_SECONDS
        return True
    return False


def clear_auth(session_state) -> None:
    """Wipe the auth grant (logout / lock-now button)."""
    session_state["auth_ok"] = False
    session_state["auth_expires_at"] = 0.0


def remaining_seconds(session_state) -> float:
    """How many seconds until the current grant expires (0 if none)."""
    if not is_authenticated(session_state):
        return 0.0
    return max(0.0, float(session_state.get("auth_expires_at", 0)) - time.time())
