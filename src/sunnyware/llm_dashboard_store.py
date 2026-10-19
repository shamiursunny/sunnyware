# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 212: LLM provider config overrides + detailed call logs."""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional


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


CONFIGS_FILE = "llm_provider_configs.json"
LOGS_FILE = "llm_call_logs.json"
PRIORITY_FILE = "llm_priority_order.json"
MAX_LOGS = 5000

DEFAULT_LIMITS = {
    "limit_per_min": 30,
    "limit_per_hour": 500,
    "limit_per_day": 5000,
    "enabled": True,
    "model_override": "",
    "max_tokens": 2048,
    "temperature": 0.7,
}


# ═══════════════════════════════════════════════════════════
# PROVIDER CONFIGS
# ═══════════════════════════════════════════════════════════
def get_provider_config(provider: str) -> dict:
    configs = _load(CONFIGS_FILE, {})
    base = dict(DEFAULT_LIMITS)
    base.update(configs.get(provider, {}))
    return base


def set_provider_config(provider: str, patch: dict) -> dict:
    configs = _load(CONFIGS_FILE, {})
    current = configs.get(provider, {})
    current.update(patch)
    configs[provider] = current
    _save(CONFIGS_FILE, configs)
    return get_provider_config(provider)


def list_all_configs() -> dict:
    configs = _load(CONFIGS_FILE, {})
    return {p: get_provider_config(p) for p in configs}


# ═══════════════════════════════════════════════════════════
# PRIORITY ORDER
# ═══════════════════════════════════════════════════════════
def set_priority_order(providers: list) -> None:
    _save(PRIORITY_FILE, {"order": list(providers), "updated_at": time.time()})


def get_priority_order() -> list:
    d = _load(PRIORITY_FILE, {"order": []})
    return d.get("order", [])


# ═══════════════════════════════════════════════════════════
# LLM CALL LOGS
# ═══════════════════════════════════════════════════════════
def log_llm_call(provider: str, model: str, ok: bool, tokens: int = 0,
                 latency_ms: float = 0, error: str = "", user: str = "") -> dict:
    logs = _load(LOGS_FILE, {})
    lid = "l_" + secrets.token_hex(6)
    entry = {
        "id": lid,
        "ts": time.time(),
        "provider": provider or "",
        "model": model or "",
        "ok": bool(ok),
        "tokens": int(tokens or 0),
        "latency_ms": float(latency_ms or 0),
        "error": (error or "")[:300],
        "user": (user or "").lower(),
    }
    logs[lid] = entry
    if len(logs) > MAX_LOGS:
        items = sorted(logs.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-MAX_LOGS]:
            del logs[k]
    _save(LOGS_FILE, logs)
    return entry


def list_llm_logs(limit: int = 200, provider: str = "", errors_only: bool = False) -> list:
    logs = _load(LOGS_FILE, {})
    items = list(logs.values())
    if provider:
        items = [l for l in items if l.get("provider") == provider]
    if errors_only:
        items = [l for l in items if not l.get("ok")]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


def clear_llm_logs() -> bool:
    return _save(LOGS_FILE, {})


# ═══════════════════════════════════════════════════════════
# RATE LIMIT COUNTERS (rolling windows)
# ═══════════════════════════════════════════════════════════
COUNTERS_FILE = "llm_rate_counters.json"


def _get_counters() -> dict:
    return _load(COUNTERS_FILE, {"minute": {}, "hour": {}, "day": {}})


def _window_keys() -> tuple:
    now = time.time()
    return (
        int(now // 60),         # minute bucket
        int(now // 3600),       # hour bucket
        int(now // 86400),      # day bucket
    )


def record_call_and_check_limits(provider: str) -> dict:
    """Increment counters and return whether the call is allowed."""
    counters = _get_counters()
    cfg = get_provider_config(provider)
    mkey, hkey, dkey = _window_keys()

    def _ensure(window: str, key: int) -> dict:
        w = counters.setdefault(window, {})
        if key not in w:
            # prune old buckets (keep last 2)
            for k in list(w.keys()):
                if k < key - 1:
                    del w[k]
            w[key] = {}
        return w[key]

    mb = _ensure("minute", mkey)
    hb = _ensure("hour", hkey)
    db = _ensure("day", dkey)

    cur_min = mb.get(provider, 0)
    cur_hr = hb.get(provider, 0)
    cur_day = db.get(provider, 0)

    allowed = (
        cur_min < cfg.get("limit_per_min", 30)
        and cur_hr < cfg.get("limit_per_hour", 500)
        and cur_day < cfg.get("limit_per_day", 5000)
    )

    if allowed:
        mb[provider] = cur_min + 1
        hb[provider] = cur_hr + 1
        db[provider] = cur_day + 1
        _save(COUNTERS_FILE, counters)

    return {
        "allowed": allowed,
        "used_min": cur_min,
        "used_hour": cur_hr,
        "used_day": cur_day,
        "limit_min": cfg.get("limit_per_min", 30),
        "limit_hour": cfg.get("limit_per_hour", 500),
        "limit_day": cfg.get("limit_per_day", 5000),
    }

ORCHESTRATOR_FILE = "orchestrator_config.json"
DEFAULT_ORCHESTRATOR = {
    "disable_all": False,
    "routing_strategy": "fallback",
    "global_rate_limit": 60,
    "max_retries": 2,
    "system_prompt_addon": "",
}

def get_orchestrator_config() -> dict:
    cfg = _load(ORCHESTRATOR_FILE, {})
    base = dict(DEFAULT_ORCHESTRATOR)
    base.update(cfg)
    return base

def set_orchestrator_config(patch: dict) -> dict:
    cfg = _load(ORCHESTRATOR_FILE, {})
    cfg.update(patch)
    _save(ORCHESTRATOR_FILE, cfg)
    return get_orchestrator_config()

