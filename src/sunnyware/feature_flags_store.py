# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 224b: Feature flag management."""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

FLAGS_FILE = "feature_flags.json"
OVERRIDES_FILE = "feature_flag_overrides.json"


def _base() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


def _load(name: str) -> dict:
    p = _base() / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(name: str, data: dict) -> bool:
    p = _base() / name
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


# ─── DEFAULTS ───
DEFAULT_FLAGS = {
    "new_dashboard": {
        "name": "New Dashboard UI",
        "description": "The redesigned dashboard layout",
        "global_pct": 0,
        "enabled_orgs": [],
        "enabled_plans": [],
    },
    "beta_tools": {
        "name": "Beta Tools",
        "description": "Experimental tools (web_search_v2, code_interpreter)",
        "global_pct": 100,
        "enabled_orgs": [],
        "enabled_plans": ["pro", "enterprise"],
    },
    "extended_context": {
        "name": "Extended Context",
        "description": "Allow 200k token conversations",
        "global_pct": 0,
        "enabled_orgs": [],
        "enabled_plans": ["enterprise"],
    },
    "streaming_v2": {
        "name": "Streaming v2",
        "description": "New streaming implementation",
        "global_pct": 10,
        "enabled_orgs": [],
        "enabled_plans": [],
    },
    "dark_mode_default": {
        "name": "Dark Mode Default",
        "description": "Default new users to dark mode",
        "global_pct": 0,
        "enabled_orgs": [],
        "enabled_plans": [],
    },
}


# ─── CRUD ───
def list_flags() -> list:
    flags = _load(FLAGS_FILE)
    result = []
    for fid, spec in DEFAULT_FLAGS.items():
        merged = dict(spec)
        if fid in flags:
            merged.update(flags[fid])
        merged["id"] = fid
        result.append(merged)
    # Include any custom flags not in defaults
    for fid, spec in flags.items():
        if fid not in DEFAULT_FLAGS:
            merged = {"id": fid, "name": fid, "description": "", "global_pct": 0, "enabled_orgs": [], "enabled_plans": []}
            merged.update(spec)
            result.append(merged)
    result.sort(key=lambda x: x["id"])
    return result


def get_flag(flag_id: str) -> Optional[dict]:
    flags = _load(FLAGS_FILE)
    spec = dict(DEFAULT_FLAGS.get(flag_id, {}))
    if flag_id in flags:
        spec.update(flags[flag_id])
    if not spec:
        return None
    spec["id"] = flag_id
    return spec


def update_flag(flag_id: str, patch: dict) -> dict:
    flags = _load(FLAGS_FILE)
    current = flags.get(flag_id, {})
    # Allowed fields
    allowed = {"global_pct", "enabled_orgs", "enabled_plans"}
    for k, v in patch.items():
        if k in allowed:
            current[k] = v
    flags[flag_id] = current
    _save(FLAGS_FILE, flags)
    return get_flag(flag_id)


def create_flag(flag_id: str, name: str, description: str) -> dict:
    flags = _load(FLAGS_FILE)
    if flag_id in flags or flag_id in DEFAULT_FLAGS:
        return {"error": "Flag already exists"}
    flags[flag_id] = {
        "name": name or flag_id,
        "description": description or "",
        "global_pct": 0,
        "enabled_orgs": [],
        "enabled_plans": [],
    }
    _save(FLAGS_FILE, flags)
    return get_flag(flag_id)


def delete_flag(flag_id: str) -> bool:
    flags = _load(FLAGS_FILE)
    if flag_id not in flags:
        return False
    del flags[flag_id]
    _save(FLAGS_FILE, flags)
    # Remove any overrides
    overrides = _load(OVERRIDES_FILE)
    if flag_id in overrides:
        del overrides[flag_id]
        _save(OVERRIDES_FILE, overrides)
    return True


# ─── EVALUATION ───
def evaluate(flag_id: str, org_id: str = "", plan: str = "", user_email: str = "") -> bool:
    """Evaluate a flag for a specific org/user. Returns True if enabled."""
    flag = get_flag(flag_id)
    if not flag:
        return False

    # Explicit override
    overrides = _load(OVERRIDES_FILE)
    flag_overrides = overrides.get(flag_id, {})
    if org_id and org_id in flag_overrides:
        return bool(flag_overrides[org_id])
    if user_email and user_email in flag_overrides:
        return bool(flag_overrides[user_email])

    # Enabled orgs
    if org_id and org_id in flag.get("enabled_orgs", []):
        return True

    # Enabled plans
    if plan and plan in flag.get("enabled_plans", []):
        return True

    # Global percentage rollout (deterministic based on org_id or user_email)
    pct = int(flag.get("global_pct", 0))
    if pct <= 0:
        return False
    if pct >= 100:
        return True
    key = org_id or user_email or ""
    if not key:
        return False
    import hashlib
    h = int(hashlib.sha256((flag_id + ":" + key).encode()).hexdigest(), 16)
    bucket = h % 100
    return bucket < pct


def set_override(flag_id: str, key: str, value: bool) -> dict:
    overrides = _load(OVERRIDES_FILE)
    if flag_id not in overrides:
        overrides[flag_id] = {}
    if value:
        overrides[flag_id][key] = True
    else:
        overrides[flag_id].pop(key, None)
    _save(OVERRIDES_FILE, overrides)
    return {"ok": True}


def get_overrides(flag_id: str) -> dict:
    overrides = _load(OVERRIDES_FILE)
    return overrides.get(flag_id, {})


def evaluate_all(org_id: str = "", plan: str = "", user_email: str = "") -> dict:
    """Evaluate all flags for a given context. Used by frontend."""
    result = {}
    for flag in list_flags():
        result[flag["id"]] = evaluate(flag["id"], org_id, plan, user_email)
    return result
