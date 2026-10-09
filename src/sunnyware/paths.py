# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Path resolution for persistent storage.

Preference order:
  1. Explicit env var: SUNNYWARE_WORKSPACE / SUNNYWARE_LOGS
  2. /data/* if /data exists and is writable (HF mounted bucket)
  3. ./data/* (local development fallback)
"""

import os
from pathlib import Path


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _resolve(env_var: str, subdir: str) -> Path:
    import sys
    # 1) explicit env
    env_val = (os.getenv(env_var) or "").strip()
    if env_val:
        return Path(env_val).resolve()

    # 2) /data/<subdir> — only on POSIX (HF Spaces Linux bucket mount)
    #    On Windows, /data resolves to <drive>:\data which we don't want.
    if sys.platform != "win32":
        persistent = Path("/data") / subdir
        if _is_writable(persistent):
            return persistent.resolve()

    # 3) ./data/<subdir> (Windows + local dev fallback)
    local = Path("./data") / subdir
    try:
        local.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return local.resolve()


def workspace() -> Path:
    """Agent file sandbox — persists across HF restarts when bucket mounted."""
    return _resolve("SUNNYWARE_WORKSPACE", "workspace")


def logs_dir() -> Path:
    """Log directory — persists across HF restarts when bucket mounted."""
    return _resolve("SUNNYWARE_LOGS", "logs")


def data_root() -> Path:
    """Root data directory (parent of workspace + logs)."""
    return workspace().parent


def using_persistent_storage() -> bool:
    """True if /data is being used (HF bucket mounted)."""
    try:
        return "/data" in str(workspace())
    except Exception:
        return False


def status() -> dict:
    return {
        "workspace": str(workspace()),
        "logs": str(logs_dir()),
        "persistent": using_persistent_storage(),
    }
