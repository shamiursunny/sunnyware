# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 100 / 100b: persistent auto-learned provider prompt limits.

When a provider returns HTTP 413 ("request too large"), we learn its
actual limit from the tokens we just sent and persist it so it survives
container restarts and HF Space rebuilds.

Storage path resolution (in order):
  1. SUNNYWARE_DATA_DIR env var (explicit override)
  2. /data (HF persistent bucket, if writable)
  3. ./data (local development fallback)

Precedence (highest to lowest) for a provider's effective limit:
  1. {PREFIX}_MAX_PROMPT_TOKENS env var (explicit override)
  2. Learned limit from provider_limits.json (auto-adapted)
  3. Hardcoded default in providers.py

Writes are logged so silent failures are visible in HF Space logs.
"""
import json
import os
from pathlib import Path
from typing import Dict, Optional


_LIMITS_FILE: Optional[Path] = None
_LIMITS_PATH_SOURCE: Optional[str] = None
_LEARNED: Optional[Dict[str, int]] = None

# Safety margin when learning from a 413: we know the sent size was too
# big, so step down by this much and clamp to a minimum.
_LEARN_MARGIN = 200
_LEARN_MIN = 500


def _probe_writable(d: Path) -> bool:
    """Return True if d exists/is-creatable AND we can write a file there."""
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    probe = d / ".sunnyware_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _resolve_limits_path() -> "tuple[Path, str]":
    """Pick the storage location. Returns (path, source_label).

    source_label is one of: 'env:SUNNYWARE_DATA_DIR', 'hf:/data',
    'local:./data'. Logged once at first call.
    """
    # 1. Explicit env override
    env_dir = (os.getenv("SUNNYWARE_DATA_DIR") or "").strip()
    if env_dir:
        d = Path(env_dir)
        if _probe_writable(d):
            return d / "provider_limits.json", "env:SUNNYWARE_DATA_DIR"

    # 2. HF persistent bucket at /data (volume mount).
    # Only attempt on POSIX -- on Windows, Path("/data") resolves to
    # \data on the current drive (H:\data), which is not the HF bucket.
    if os.name == "posix":
        hf_dir = Path("/data")
        if hf_dir.is_dir() and _probe_writable(hf_dir):
            return hf_dir / "provider_limits.json", "hf:/data"

    # 3. Local dev fallback
    local_dir = Path("data")
    return local_dir / "provider_limits.json", "local:./data"


def _limits_path() -> Path:
    global _LIMITS_FILE, _LIMITS_PATH_SOURCE
    if _LIMITS_FILE is not None:
        return _LIMITS_FILE
    path, source = _resolve_limits_path()
    _LIMITS_FILE = path
    _LIMITS_PATH_SOURCE = source
    # Log the chosen path once (best-effort, never fatal)
    try:
        print(f"[provider_limits] storage source={source} path={path}",
              flush=True)
    except Exception:
        pass
    # Ensure parent dir exists (may fail silently on read-only FS)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return _LIMITS_FILE


def path_source() -> str:
    """Human-readable label of the chosen storage location (for debug)."""
    _limits_path()
    return _LIMITS_PATH_SOURCE or "unknown"


def load_learned(force_reload: bool = False) -> Dict[str, int]:
    """Load the persisted learned limits (cached after first call)."""
    global _LEARNED
    if _LEARNED is not None and not force_reload:
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
        except Exception as e:
            print(f"[provider_limits] load failed: {type(e).__name__}: {e}",
                  flush=True)
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


def _save() -> bool:
    """Persist learned limits. Returns True on success. Logs failures."""
    p = _limits_path()
    try:
        payload = json.dumps(_LEARNED or {}, indent=2, sort_keys=True)
        p.write_text(payload, encoding="utf-8")
        # Verify readable + correct
        check = json.loads(p.read_text(encoding="utf-8"))
        if check != (_LEARNED or {}):
            print(f"[provider_limits] save verification mismatch at {p}",
                  flush=True)
            return False
        return True
    except Exception as e:
        print(f"[provider_limits] save FAILED at {p}: "
              f"{type(e).__name__}: {e}", flush=True)
        return False


def reset(name: Optional[str] = None) -> bool:
    """Clear learned limits (all, or one provider). Returns save success."""
    learned = load_learned()
    if name:
        learned.pop(name, None)
    else:
        learned.clear()
    return _save()


def snapshot() -> Dict[str, int]:
    """Read-only copy of learned limits (for /api/providers/status)."""
    return dict(load_learned())


def debug_info() -> dict:
    """Diagnostic snapshot for /api/providers/limits (Part 100b)."""
    p = _limits_path()
    info = {
        "path": str(p),
        "path_source": path_source(),
        "parent_exists": p.parent.is_dir(),
        "parent_writable": _probe_writable(p.parent) if p.parent.is_dir() else False,
        "file_exists": p.is_file(),
        "learned": dict(load_learned()),
    }
    if p.is_file():
        try:
            info["file_size"] = p.stat().st_size
            info["file_mtime"] = p.stat().st_mtime
            info["file_content"] = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            info["file_read_error"] = f"{type(e).__name__}: {e}"
    return info
