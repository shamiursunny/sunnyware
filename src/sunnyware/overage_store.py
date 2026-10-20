# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 224c: Usage overage billing."""

import json
import os
import time
from pathlib import Path
from typing import Optional

CHARGES_FILE = "overage_charges.json"
CONFIG_FILE = "overage_config.json"

DEFAULT_CONFIG = {
    "rate_per_million": 0.50,   # $0.50 per 1M overage tokens
    "enabled": True,
}

DEFAULT_OVERAGE_CAPS = {
    "free": {
        "hard_cap": True,        # No overage allowed
        "overage_limit_millions": 0,
    },
    "pro": {
        "hard_cap": False,
        "overage_limit_millions": 50,   # Up to 50M overage (soft)
    },
    "enterprise": {
        "hard_cap": False,
        "overage_limit_millions": -1,   # Unlimited
    },
}


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


# ─── CONFIG ───
def get_config() -> dict:
    cfg = _load(CONFIG_FILE)
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    return merged


def update_config(patch: dict) -> dict:
    cfg = _load(CONFIG_FILE)
    for k in ("rate_per_million", "enabled"):
        if k in patch:
            cfg[k] = patch[k]
    _save(CONFIG_FILE, cfg)
    return get_config()


def get_overage_caps() -> dict:
    """Per-plan overage caps. Stored with the config so they can be adjusted."""
    cfg = _load(CONFIG_FILE)
    return cfg.get("caps", DEFAULT_OVERAGE_CAPS)


def update_overage_caps(caps: dict) -> dict:
    cfg = _load(CONFIG_FILE)
    cfg["caps"] = caps
    _save(CONFIG_FILE, cfg)
    return get_overage_caps()


# ─── OVERAGE CALCULATION ───
def compute_overage(org_id: str, plan: str, token_limit_millions: int, tokens_used: int) -> dict:
    """
    Compute overage for an org this month.
    Returns {tokens_used, token_limit, overage_tokens, overage_cost, hard_cap, can_continue}
    """
    cfg = get_config()
    caps = get_overage_caps()
    plan_cap = caps.get(plan, {})

    limit_tokens = 0
    if token_limit_millions and token_limit_millions > 0:
        limit_tokens = int(token_limit_millions * 1_000_000)

    overage_tokens = 0
    if limit_tokens > 0 and tokens_used > limit_tokens:
        overage_tokens = tokens_used - limit_tokens
    elif limit_tokens < 0:
        # Unlimited plan
        overage_tokens = 0

    rate = float(cfg.get("rate_per_million", 0.50))
    overage_cost = (overage_tokens / 1_000_000.0) * rate
    hard_cap = bool(plan_cap.get("hard_cap", False))

    # Can continue if hard_cap is False OR overage is under the overage limit
    can_continue = True
    if hard_cap and overage_tokens > 0:
        can_continue = False
    else:
        overage_limit_m = plan_cap.get("overage_limit_millions", -1)
        if overage_limit_m != -1:
            overage_limit_tokens = int(overage_limit_m * 1_000_000)
            if overage_tokens > overage_limit_tokens:
                can_continue = False

    return {
        "tokens_used": tokens_used,
        "token_limit": limit_tokens,
        "overage_tokens": overage_tokens,
        "overage_cost": round(overage_cost, 2),
        "rate_per_million": rate,
        "hard_cap": hard_cap,
        "can_continue": can_continue,
        "plan": plan,
    }


# ─── CHARGE LOG ───
def record_charge(org_id: str, plan: str, tokens: int, amount: float, note: str = "") -> dict:
    """Log an overage charge for billing history."""
    charges = _load(CHARGES_FILE)
    cid = "ovg_" + str(int(time.time())) + "_" + org_id[-6:]
    charges[cid] = {
        "id": cid,
        "org_id": org_id,
        "plan": plan,
        "tokens": int(tokens),
        "amount": round(float(amount), 2),
        "note": note[:200],
        "ts": time.time(),
    }
    # Keep last 2000
    if len(charges) > 2000:
        items = sorted(charges.items(), key=lambda kv: kv[1].get("ts", 0))
        for k, _ in items[:-2000]:
            del charges[k]
    _save(CHARGES_FILE, charges)
    return charges[cid]


def list_charges(org_id: str = "", limit: int = 100) -> list:
    charges = _load(CHARGES_FILE)
    items = list(charges.values())
    if org_id:
        items = [c for c in items if c.get("org_id") == org_id]
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[:limit]


def clear_charges() -> bool:
    return _save(CHARGES_FILE, {})
