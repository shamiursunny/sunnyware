# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 100: persistent auto-learned provider prompt limits.

When a provider returns HTTP 413 ("request too large"), we learn its
actual limit from the tokens we just sent and persist it to disk so it
survives restarts and HF Space rebuilds.

Precedence (highest to lowest):
  1. {PREFIX}_MAX_PROMPT_TOKENS env var (explicit override)
  2. Learned limit from data/provider_limits.json (auto-adapted)
  3. Hardcoded default in providers.py

Data path:
  - SUNNYWARE_DATA_DIR env var, if set
  - /data on Hugging Face Spaces (SPACE_ID present)
  - ./data locally
"""
import json
import os
from pathlib import Path
from typing import Dict, Optional


_LIMITS_FILE: Optional[Path] = None
_LEARNED: Optional[Dict[str, int]] = None

# Safety margin when learning from a 413: we know the sent size was too
# big, so step down by this much and clamp to a minimum.
_LEARN_MARGIN = 200
_LEARN_MIN = 500


def _limits_path() -> Path:
    global _LIMITS_FILE
    if _LIMITS_FILE is not None:
        return _LIMITS_FILE
    d = os.getenv("SUNNYWARE_DATA_DIR")
    if d:
        p = Path(d)
    elif os.getenv("SPACE_ID") and Path("/data").is_dir():
        p = Path("/data")
    else:
        p = Path("data")
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    _LIMITS_FILE = p / "provider_limits.json"
    return _LIMITS_FILE


def load_learned() -> Dict[str, int]:
    """Load the persisted learned limits (cached after first call)."""
    global _LEARNED
    if _LEARNED is not None:
        return _LEARNED
    p = _limits_path()
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _LEARNED = {str(k): int(v) for k, v in data.items()
                            if isinstance(v, (int, float))}
            else:
                _LEARNED = {}
        except Exception:
            _LEARNED = {}
    else:
        _LEARNED = {}
    return _LEARNED


def get_learned(name: str) -> Optional[int]:
    """Return the learned limit for a provider, or None if we never learned."""
    v = load_learned().get(name)
    return int(v) if v is not None else None


def learn_limit(name: str, sent_tokens: int, current_limit: int = 0) -> int:
    """Called after HTTP 413. Computes a new (lower) limit from the
    tokens we just sent. Returns the new limit.

    Never raises an existing learned limit. Never returns below _LEARN_MIN.
    """
    try:
        sent_tokens = int(sent_tokens)
    except (TypeError, ValueError):
        return current_limit or 0

    new_limit = max(_LEARN_MIN, sent_tokens - _LEARN_MARGIN)

    # Don't raise a limit we already knew was lower
    if current_limit and current_limit < new_limit:
        return current_limit

    learned = load_learned()
    prev = learned.get(name)
    if prev is None or new_limit < prev:
        learned[name] = new_limit
        _save()
    return new_limit


def _save() -> None:
    p = _limits_path()
    try:
        p.write_text(json.dumps(_LEARNED or {}, indent=2, sort_keys=True),
                     encoding="utf-8")
    except Exception:
        pass


def reset(name: Optional[str] = None) -> None:
    """Clear learned limits (all, or one provider). For admin use."""
    learned = load_learned()
    if name:
        learned.pop(name, None)
    else:
        learned.clear()
    _save()


def snapshot() -> Dict[str, int]:
    """Read-only copy of learned limits (for /api/providers/status)."""
    return dict(load_learned())
