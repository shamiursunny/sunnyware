# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 212: User analytics event log (chat, tool, session)."""

import contextvars
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

# ─── Request-scoped context ───
_current_user = contextvars.ContextVar("analytics_user", default="")
_current_org = contextvars.ContextVar("analytics_org", default="")


def set_current(user: str, org: str = "") -> None:
    _current_user.set(user or "")
    _current_org.set(org or "")


def get_current() -> tuple:
    return _current_user.get(), _current_org.get()


# ─── Storage helpers ───
def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _path(name: str) -> Path:
    return _base() / name


def _load(name: str, default: dict) -> dict:
    p = _path(name)
    if not p.exists():
        return dict(default)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _save(name: str, data: dict) -> bool:
    p = _path(name)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


EVENTS_FILE = "analytics_events.json"
MAX_EVENTS = 50000


# ═══════════════════════════════════════════════════════════
# EVENT LOG
# ═══════════════════════════════════════════════════════════
def log_event(user: str, event_type: str, **kwargs) -> dict:
    """event_type: 'chat', 'tool', 'login', 'logout'
    kwargs: org_id, provider, model, tokens, tokens_in, tokens_out,
            latency_ms, ok, error, tool_name, details
    """
    events = _load(EVENTS_FILE, {})
    eid = "e_" + secrets.token_hex(6)
    entry = {
        "id": eid,
        "ts": time.time(),
        "user": (user or "").lower().strip(),
        "type": event_type,
        "org_id": kwargs.get("org_id", ""),
        "provider": kwargs.get("provider", ""),
        "model": kwargs.get("model", ""),
        "tokens": int(kwargs.get("tokens", 0) or 0),
        "tokens_in": int(kwargs.get("tokens_in", 0) or 0),
        "tokens_out": int(kwargs.get("tokens_out", 0) or 0),
        "latency_ms": float(kwargs.get("latency_ms", 0) or 0),
        "ok": bool(kwargs.get("ok", True)),
        "error": (kwargs.get("error") or "")[:500],
        "tool_name": kwargs.get("tool_name", ""),
        "details": (kwargs.get("details") or "")[:500],
    }
    events[eid] = entry
    if len(events) > MAX_EVENTS:
        items = sorted(events.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-MAX_EVENTS]:
            del events[k]
    _save(EVENTS_FILE, events)
    return entry


def list_events(user: str = "", event_type: str = "", since_ts: Optional[float] = None,
                limit: int = 500) -> list:
    events = _load(EVENTS_FILE, {})
    items = list(events.values())
    if user:
        items = [e for e in items if (e.get("user") or "") == user.lower()]
    if event_type:
        items = [e for e in items if e.get("type") == event_type]
    if since_ts:
        items = [e for e in items if (e.get("ts", 0) or 0) >= since_ts]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


# ═══════════════════════════════════════════════════════════
# AGGREGATION
# ═══════════════════════════════════════════════════════════
def _agg(events: list) -> dict:
    return {
        "tokens": sum(e.get("tokens", 0) for e in events if e.get("type") == "chat"),
        "chats": sum(1 for e in events if e.get("type") == "chat"),
        "tools": sum(1 for e in events if e.get("type") == "tool"),
        "sessions": sum(1 for e in events if e.get("type") == "login"),
        "errors": sum(1 for e in events if not e.get("ok", True)),
        "active_seconds": _session_active_seconds(events),
    }


def _session_active_seconds(events: list) -> int:
    """Pair login/logout to estimate active time."""
    total = 0.0
    login_ts = None
    for e in sorted(events, key=lambda x: x.get("ts", 0)):
        if e.get("type") == "login":
            login_ts = e.get("ts", 0)
        elif e.get("type") == "logout" and login_ts:
            total += e.get("ts", 0) - login_ts
            login_ts = None
    if login_ts:  # still logged in
        total += time.time() - login_ts
    return int(total)


def user_summary(email: str, days: int = 30) -> dict:
    now = time.time()
    day_ago = now - 86400
    week_ago = now - 7 * 86400
    month_ago = now - days * 86400
    events = list_events(user=email, since_ts=month_ago, limit=200000)

    today_events = [e for e in events if e.get("ts", 0) >= day_ago]
    week_events = [e for e in events if e.get("ts", 0) >= week_ago]

    last_login_ts = next((e["ts"] for e in events if e.get("type") == "login"), None)
    last_logout_ts = next((e["ts"] for e in events if e.get("type") == "logout"), None)

    return {
        "user": email,
        "today": _agg(today_events),
        "week": _agg(week_events),
        "month": _agg(events),
        "last_active": events[0].get("ts") if events else None,
        "last_login": last_login_ts,
        "last_logout": last_logout_ts,
    }


def daily_usage(email: str, days: int = 7) -> list:
    now = time.time()
    start = now - days * 86400
    events = list_events(user=email, since_ts=start, limit=200000)
    by_day = {}
    for e in events:
        d = time.strftime("%Y-%m-%d", time.localtime(e.get("ts", 0)))
        bucket = by_day.setdefault(d, {"date": d, "tokens": 0, "chats": 0, "tools": 0, "sessions": 0, "errors": 0})
        if e.get("type") == "chat":
            bucket["tokens"] += e.get("tokens", 0)
            bucket["chats"] += 1
        elif e.get("type") == "tool":
            bucket["tools"] += 1
        elif e.get("type") == "login":
            bucket["sessions"] += 1
        if not e.get("ok", True):
            bucket["errors"] += 1
    result = []
    for i in range(days):
        day = time.strftime("%Y-%m-%d", time.localtime(now - i * 86400))
        result.append(by_day.get(day, {"date": day, "tokens": 0, "chats": 0, "tools": 0, "sessions": 0, "errors": 0}))
    return list(reversed(result))


def all_users_summary(days: int = 30) -> list:
    now = time.time()
    since = now - days * 86400
    events = list_events(since_ts=since, limit=200000)
    users = sorted(set((e.get("user") or "").lower() for e in events if e.get("user")))
    return [user_summary(u, days) for u in users]


def stats_overview(days: int = 30) -> dict:
    now = time.time()
    since = now - days * 86400
    events = list_events(since_ts=since, limit=200000)
    by_type = {}
    for t in ["chat", "tool", "login", "logout"]:
        by_type[t] = sum(1 for e in events if e.get("type") == t)
    return {
        "total_events": len(events),
        "unique_users": len(set((e.get("user") or "") for e in events if e.get("user"))),
        "total_tokens": sum(e.get("tokens", 0) for e in events if e.get("type") == "chat"),
        "total_chats": by_type["chat"],
        "total_tools": by_type["tool"],
        "total_errors": sum(1 for e in events if not e.get("ok", True)),
        "by_type": by_type,
    }


def clear_events() -> bool:
    return _save(EVENTS_FILE, {})
