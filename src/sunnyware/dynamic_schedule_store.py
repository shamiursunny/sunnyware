# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""JSON persistence for dynamic schedules (replaces DuckDB fallback)."""

import json
import os
import time
from pathlib import Path
from typing import Optional


def _file_path() -> Path:
    data = Path(os.environ.get("SUNNYWARE_DATA_DIR", "/data"))
    if data.exists() and os.access(str(data), os.W_OK):
        return data / "dynamic_schedules.json"
    return Path("data") / "dynamic_schedules.json"


def _load() -> dict:
    p = _file_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> bool:
    p = _file_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def get(name: str) -> Optional[dict]:
    entry = _load().get(name)
    return entry


def list_all() -> list:
    data = _load()
    items = []
    for name, entry in data.items():
        items.append({
            "name": name,
            "prompt": entry.get("prompt", ""),
            "interval_seconds": int(entry.get("interval_seconds", 60)),
            "notify_email": entry.get("notify_email", ""),
            "enabled": bool(entry.get("enabled", True)),
            "last_run_at": entry.get("last_run_at"),
            "last_status": entry.get("last_status"),
            "last_result_preview": entry.get("last_result_preview"),
            "last_error": entry.get("last_error"),
            "run_count": int(entry.get("run_count", 0)),
            "created_at": float(entry.get("created_at", 0)),
        })
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items


def upsert(name: str, prompt: str, interval_seconds: int,
           notify_email: str = "", enabled: bool = True) -> dict:
    data = _load()
    existing = data.get(name, {})
    data[name] = {
        "name": name,
        "prompt": prompt,
        "interval_seconds": int(interval_seconds),
        "notify_email": notify_email,
        "enabled": enabled,
        "last_run_at": existing.get("last_run_at"),
        "last_status": existing.get("last_status"),
        "last_result_preview": existing.get("last_result_preview"),
        "last_error": existing.get("last_error"),
        "run_count": int(existing.get("run_count", 0)),
        "created_at": existing.get("created_at", time.time()),
    }
    _save(data)
    return data[name]


def delete(name: str) -> bool:
    data = _load()
    if name in data:
        del data[name]
        _save(data)
        return True
    return False


def update_run_info(name: str, status: str, preview: str, error: str = "") -> bool:
    data = _load()
    if name not in data:
        return False
    entry = data[name]
    entry["last_run_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    entry["last_status"] = status
    entry["last_result_preview"] = preview[:500]
    entry["last_error"] = error
    entry["run_count"] = int(entry.get("run_count", 0)) + 1
    _save(data)
    return True
