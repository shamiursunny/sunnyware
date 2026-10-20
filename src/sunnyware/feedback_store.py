# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 225: User feedback collection."""

import json
import os
import secrets
import time
from pathlib import Path

FEEDBACK_FILE = "feedback.json"


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _load() -> dict:
    p = _base() / FEEDBACK_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> bool:
    p = _base() / FEEDBACK_FILE
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def add(rating: int, comment: str, user: str = "", page: str = "") -> dict:
    entries = _load()
    fid = "fb_" + secrets.token_hex(8)
    entry = {
        "id": fid,
        "ts": time.time(),
        "rating": max(1, min(5, int(rating))),
        "comment": (comment or "")[:2000],
        "user": (user or "")[:120],
        "page": (page or "")[:200],
    }
    entries[fid] = entry
    if len(entries) > 5000:
        items = sorted(entries.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-5000]:
            del entries[k]
    _save(entries)
    return entry


def list_entries(limit: int = 200) -> list:
    entries = _load()
    items = list(entries.values())
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


def clear() -> bool:
    return _save({})


def stats() -> dict:
    entries = _load()
    values = list(entries.values())
    if not values:
        return {"count": 0, "avg_rating": 0, "ratings": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}}
    ratings = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    total = 0
    for e in values:
        r = e.get("rating", 0)
        if r in ratings:
            ratings[r] += 1
        total += r
    return {
        "count": len(values),
        "avg_rating": round(total / len(values), 2) if values else 0,
        "ratings": ratings,
    }
