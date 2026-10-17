# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 172: per-tool health aggregator."""

def _get_all_tools():
    try:
        from .tools import _TOOLS
        return _TOOLS
    except Exception:
        return {}


def _get_tool_categories():
    try:
        from .tools import _TOOLS
    except Exception:
        return {}
    out = {}
    for name, tool in _TOOLS.items():
        mod = getattr(tool.__class__, "__module__", "") or ""
        leaf = mod.rsplit(".", 1)[-1] if "." in mod else mod
        if any(k in leaf for k in ("memory", "recall")):
            cat = "memory"
        elif any(k in leaf for k in ("csv", "excel", "pdf", "doc",
                                     "data_quality", "report", "chart")):
            cat = "data"
        elif any(k in leaf for k in ("web", "search", "fetch", "research")):
            cat = "web"
        elif any(k in leaf for k in ("file", "workspace", "dir")):
            cat = "files"
        elif any(k in leaf for k in ("kpi", "schedule", "webhook",
                                     "dynamic")):
            cat = "workflow"
        elif any(k in leaf for k in ("sql", "duckdb")):
            cat = "sql"
        elif any(k in leaf for k in ("role", "delegate", "auditor",
                                     "agent")):
            cat = "roles"
        elif any(k in leaf for k in ("calculator", "echo", "time",
                                     "python", "citation")):
            cat = "core"
        else:
            cat = "other"
        out[name] = cat
    return out


def _tool_health(name, tool, breaker_state, fails_threshold):
    b = breaker_state or {}
    is_open = bool(b.get("open"))
    consecutive = int(b.get("consecutive_fails", 0))
    total_fails = int(b.get("total_fails", 0))
    total_success = int(b.get("total_success", 0))
    last_err = str(b.get("last_error", ""))[:300]
    remaining = int(b.get("remaining_open_s", 0))

    rate_cool = int(b.get("rate_cooldown_s", 0))
    rpm_limit = int(b.get("rpm_limit", 0))
    rpm_current = int(b.get("rpm_current", 0))

    if is_open:
        status = "broken"
        reason = last_err or "circuit open after repeated failures"
    elif rate_cool > 0:
        status = "degraded"
        reason = f"rate limited ({rpm_current}/{rpm_limit} rpm) - cooldown {rate_cool}s"
    elif consecutive >= 3:
        status = "degraded"
        reason = last_err or f"{consecutive} consecutive failures"
    elif total_fails == 0 and total_success == 0:
        status = "never_used"
        reason = "no calls recorded"
    elif consecutive >= 1:
        status = "working"
        reason = last_err or ""
    else:
        status = "working"
        reason = ""

    return {
        "name": name,
        "status": status,
        "is_open": is_open,
        "consecutive_fails": consecutive,
        "total_fails": total_fails,
        "total_success": total_success,
        "last_error": last_err,
        "remaining_open_s": remaining,
        "rpm_limit": rpm_limit,
        "rpm_current": rpm_current,
        "rate_cooldown_s": rate_cool,
        "reason": reason,
    }


def snapshot():
    try:
        from . import circuit_breaker as cb
        breaker_snap = cb.snapshot()
    except Exception:
        breaker_snap = {"tools": [], "fails_threshold": 5}

    fails_threshold = int(breaker_snap.get("fails_threshold", 5))
    breaker_map = {t["name"]: t for t in (breaker_snap.get("tools") or [])}

    try:
        all_tools = _get_all_tools()
        cats = _get_tool_categories()
    except Exception:
        all_tools = {}
        cats = {}

    tools_list = []
    for name in all_tools:
        h = _tool_health(name, all_tools[name],
                         breaker_map.get(name), fails_threshold)
        h["category"] = cats.get(name, "other")
        tools_list.append(h)

    priority = {"broken": 0, "degraded": 1, "working": 2, "never_used": 3}
    tools_list.sort(key=lambda t: (priority.get(t["status"], 9),
                                    t["name"]))

    summary = {
        "total": len(tools_list),
        "working": 0,
        "degraded": 0,
        "broken": 0,
        "never_used": 0,
    }
    for t in tools_list:
        if t["status"] in summary:
            summary[t["status"]] += 1

    groups = {}
    for t in tools_list:
        groups.setdefault(t["category"], []).append(t)

    return {
        "summary": summary,
        "groups": groups,
        "tools": tools_list,
        "breaker_threshold": fails_threshold,
    }


def get_tool_health(name):
    for t in snapshot().get("tools", []):
        if t.get("name") == name:
            return t
    return None
