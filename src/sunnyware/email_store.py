# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 217: Email logs."""

import json
import os
import secrets
import time
from pathlib import Path

def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")

def _load(name: str, default: dict) -> dict:
    p = _base() / name
    if not p.exists(): return dict(default)
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return dict(default)

def _save(name: str, data: dict) -> bool:
    p = _base() / name
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception: return False

LOGS_FILE = "email_logs.json"

def log_email(to: str, subject: str, status: str, error: str = "") -> dict:
    logs = _load(LOGS_FILE, {})
    eid = "em_" + secrets.token_hex(6)
    entry = {
        "id": eid,
        "ts": time.time(),
        "to": to,
        "subject": subject,
        "status": status,
        "error": error[:300],
    }
    logs[eid] = entry
    if len(logs) > 2000:
        items = sorted(logs.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-2000]:
            del logs[k]
    _save(LOGS_FILE, logs)
    return entry

def list_emails(limit: int = 100) -> list:
    logs = _load(LOGS_FILE, {})
    items = list(logs.values())
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]

def clear_emails() -> bool:
    return _save(LOGS_FILE, {})
