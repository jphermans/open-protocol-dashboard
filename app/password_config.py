"""Persistent storage for the destructive-actions password.

Sits next to ``db_config.json`` so the operator can change the password
from the Setup tab and have it survive an app restart / venv rebuild.

Schema (UTF-8 JSON, single key):

    {
        "password_hash": "<64-char lowercase hex SHA-256>"
    }

Resolution order used by ``app.auth.get_password_hash``:

    1. ``OPEN_PROTOCOL_PASSWORD_HASH`` env var   (operator override)
    2. ``auth_config.json`` on disk             (this module)
    3. Built-in default ``Atlas123!``            (when no file exists)

When the file does not exist (fresh clone, fresh venv, after a
``--recreate-venv``, after a manual ``rm auth_config.json``), the
built-in default password is used. This is the "When reinstalling
then use standard password" behaviour: a missing file is treated as
a request to fall back to the factory default, not as an error.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from app.paths import PROJECT_DIR

CONFIG_FILE = PROJECT_DIR / "auth_config.json"


def _default_hash() -> str:
    """SHA-256 of the built-in default password with the static salt."""
    from app.auth import DEFAULT_PASSWORD, _SALT   # late import to avoid cycle
    return hashlib.sha256((_SALT + DEFAULT_PASSWORD).encode("utf-8")).hexdigest()


def _is_valid_hash(value: str) -> bool:
    """True if ``value`` looks like a 64-char lowercase hex SHA-256."""
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value.lower())


def load_password_hash() -> Optional[str]:
    """Return the custom password hash from disk, or ``None``.

    Returns ``None`` when:
        * the file does not exist (fresh install / reset to default)
        * the file is malformed (treated as "use default" so the
          dashboard stays bootable; the operator can fix via Setup)
        * the stored hash is the same as the default hash (no
          behavioural difference — but we still return it so the UI
          can show "Custom" instead of "Default" if it wants to)
    """
    if not CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = (data or {}).get("password_hash")
    if not _is_valid_hash(value):
        return None
    return value.lower()


def save_password_hash(hash_hex: str) -> None:
    """Write ``hash_hex`` to ``auth_config.json`` atomically.

    Raises ``ValueError`` if the hash is not a valid 64-char hex string.
    Raises ``OSError`` if the file cannot be written.
    """
    if not _is_valid_hash(hash_hex):
        raise ValueError("password_hash must be 64 lowercase hex chars (SHA-256)")
    payload = {"password_hash": hash_hex.lower()}
    tmp = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, CONFIG_FILE)


def clear_password_hash() -> bool:
    """Delete ``auth_config.json`` if it exists.

    Returns True if a file was removed, False if there was nothing to
    remove. Missing file is treated as success (the goal is "use
    default").
    """
    if not CONFIG_FILE.exists():
        return False
    CONFIG_FILE.unlink()
    return True


def is_using_default() -> bool:
    """True if the active password is the built-in default."""
    return get_active_hash() == _default_hash()


def get_active_hash() -> str:
    """Resolve the active password hash with full precedence:

        1. ``OPEN_PROTOCOL_PASSWORD_HASH`` env var.
        2. ``auth_config.json`` on disk (this module).
        3. Built-in default (``Atlas123!``).
    """
    override = os.environ.get("OPEN_PROTOCOL_PASSWORD_HASH", "").strip().lower()
    if override and _is_valid_hash(override):
        return override
    disk = load_password_hash()
    if disk:
        return disk
    return _default_hash()


def hash_password(plaintext: str) -> str:
    """Compute the SHA-256 hash of ``plaintext`` using the static salt.

    Convenience helper so the UI layer doesn't need to import the
    salt from ``app.auth`` directly.
    """
    from app.auth import _SALT
    return hashlib.sha256((_SALT + plaintext).encode("utf-8")).hexdigest()