# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Request-scoped tenant context (per-API-key session isolation).

Middleware sets the current key. sessions.py reads it to scope queries.
Auth OFF → key is empty string → owner_key = '' → shared (legacy) behavior.
"""

import contextvars


_current_key: contextvars.ContextVar = contextvars.ContextVar(
    "current_api_key", default=""
)


def set_key(key: str) -> None:
    try:
        _current_key.set(key or "")
    except Exception:
        pass


def get_key() -> str:
    try:
        return _current_key.get() or ""
    except Exception:
        return ""


def reset() -> None:
    try:
        _current_key.set("")
    except Exception:
        pass
