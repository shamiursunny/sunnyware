# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 182: SaaS data stores (orgs, plans, subs, invoices, notes)."""

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

DEFAULT_PLANS = {
    "free": {
        "id": "free", "name": "Free", "price_monthly": 0,
        "calls_per_day": 100, "max_api_keys": 1,
        "token_limit_millions": 1, "trial_days": 0, "annual_discount_pct": 0,
        "paddle_product_id": "", "paddle_price_id": "",
        "features": ["Basic tools", "Community support"], "created_at": 0,
    },
    "pro": {
        "id": "pro", "name": "Pro", "price_monthly": 49,
        "calls_per_day": 10000, "max_api_keys": 5,
        "token_limit_millions": 20, "trial_days": 0, "annual_discount_pct": 0,
        "paddle_product_id": "", "paddle_price_id": "",
        "features": ["All tools", "Priority support", "HITL approvals"], "created_at": 0,
    },
    "enterprise": {
        "id": "enterprise", "name": "Enterprise", "price_monthly": 299,
        "calls_per_day": -1, "max_api_keys": -1,
        "token_limit_millions": -1, "trial_days": 0, "annual_discount_pct": 0,
        "paddle_product_id": "", "paddle_price_id": "",
        "features": ["Unlimited", "SLA", "Dedicated support", "SSO"], "created_at": 0,
    },
}

def _seed_plans() -> dict:
    plans = _load("plans.json", {})
    if not plans:
        plans = dict(DEFAULT_PLANS)
        for k in plans:
            plans[k]["created_at"] = time.time()
        _save("plans.json", plans)
    # Part 203: migrate legacy plans missing token_limit_millions
    _changed = False
    for _pid, _pl in plans.items():
        if "token_limit_millions" not in _pl:
            _default = DEFAULT_PLANS.get(_pid, {}).get("token_limit_millions", -1)
            _pl["token_limit_millions"] = _default
            _changed = True
    if _changed:
        _save("plans.json", plans)
    return plans

def list_orgs() -> list:
    orgs = _load("orgs.json", {})
    return sorted(orgs.values(), key=lambda o: o.get("created_at", 0), reverse=True)

def get_org(org_id: str) -> Optional[dict]:
    return _load("orgs.json", {}).get(org_id)

def create_org(name: str, plan: str = "free", owner_email: str = "", workos_org_id: str = "") -> dict:
    orgs = _load("orgs.json", {})
    oid = "org_" + secrets.token_hex(6)
    org = {
        "id": oid, "name": name, "plan": plan, "owner_email": owner_email,
        "workos_org_id": workos_org_id, "status": "active",
        "stripe_customer_id": "", "paddle_customer_id": "",
        "created_at": time.time(),
    }
    orgs[oid] = org
    _save("orgs.json", orgs)
    return org

def update_org(org_id: str, patch: dict) -> Optional[dict]:
    orgs = _load("orgs.json", {})
    if org_id not in orgs:
        return None
    orgs[org_id].update(patch)
    _save("orgs.json", orgs)
    return orgs[org_id]

def delete_org(org_id: str) -> bool:
    orgs = _load("orgs.json", {})
    if org_id in orgs:
        del orgs[org_id]
        _save("orgs.json", orgs)
        return True
    return False

def list_plans() -> list:
    return list(_seed_plans().values())

def update_plan(plan_id: str, patch: dict) -> Optional[dict]:
    plans = _seed_plans()
    if plan_id not in plans:
        return None
    plans[plan_id].update(patch)
    _save("plans.json", plans)
    return plans[plan_id]

def list_subs() -> list:
    subs = _load("subs.json", {})
    return sorted(subs.values(), key=lambda s: s.get("created_at", 0), reverse=True)

def create_sub(org_id: str, plan_id: str, status: str = "active", stripe_sub_id: str = "") -> dict:
    subs = _load("subs.json", {})
    sid = "sub_" + secrets.token_hex(6)
    now = time.time()
    sub = {
        "id": sid, "org_id": org_id, "plan_id": plan_id, "status": status,
        "stripe_sub_id": stripe_sub_id, "current_period_start": now,
        "current_period_end": now + 30 * 86400, "created_at": now,
    }
    subs[sid] = sub
    _save("subs.json", subs)
    return sub

def list_invoices() -> list:
    invs = _load("invoices.json", {})
    return sorted(invs.values(), key=lambda i: i.get("created_at", 0), reverse=True)

def create_invoice(org_id: str, amount: float, description: str = "", status: str = "paid") -> dict:
    invs = _load("invoices.json", {})
    iid = "inv_" + secrets.token_hex(6)
    now = time.time()
    inv = {
        "id": iid, "org_id": org_id, "amount_cents": int(round(amount * 100)),
        "currency": "usd", "description": description, "status": status, "created_at": now,
    }
    invs[iid] = inv
    _save("invoices.json", invs)
    return inv

def list_notes(org_id: Optional[str] = None) -> list:
    notes = _load("notes.json", {})
    out = list(notes.values())
    if org_id:
        out = [n for n in out if n.get("org_id") == org_id]
    return sorted(out, key=lambda n: n.get("created_at", 0), reverse=True)

def create_note(org_id: str, text: str, author: str = "admin") -> dict:
    notes = _load("notes.json", {})
    nid = "note_" + secrets.token_hex(6)
    note = {"id": nid, "org_id": org_id, "text": text, "author": author, "created_at": time.time()}
    notes[nid] = note
    _save("notes.json", notes)
    return note

def dashboard_stats() -> dict:
    orgs = list_orgs()
    plans = {p["id"]: p for p in list_plans()}
    subs = [s for s in list_subs() if s.get("status") == "active"]
    invoices = list_invoices()
    total_mrr = sum(plans.get(o.get("plan", "free"), {}).get("price_monthly", 0) for o in orgs)
    total_revenue = sum(i.get("amount_cents", 0) for i in invoices if i.get("status") == "paid") / 100.0
    return {
        "total_orgs": len(orgs), "active_orgs": len([o for o in orgs if o.get("status") == "active"]),
        "total_subs": len(subs), "mrr": total_mrr, "arr": total_mrr * 12,
        "total_revenue": total_revenue, "total_invoices": len(invoices),
        "total_notes": len(list_notes()),
    }

def get_org_for_api_key(api_key: str) -> Optional[dict]:
    """Find the SaaS Org associated with an SSO API key."""
    if not api_key:
        return None
    try:
        from . import user_store as _us
        email = _us.email_for_api_key(api_key)
        if not email:
            return None
        user = _us.get(email)
        if not user:
            return None
        workos_org_id = user.get("org_id")
        if not workos_org_id:
            return None
        orgs = _load("orgs.json", {})
        for o in orgs.values():
            if o.get("workos_org_id") == workos_org_id:
                return o
    except Exception:
        pass
    return None

def get_or_create_for_workos(workos_org_id: str, owner_email: str = "") -> dict:
    """Find or create a SaaS Org for a WorkOS Organization ID."""
    if not workos_org_id:
        return None
    orgs = _load("orgs.json", {})
    for o in orgs.values():
        if o.get("workos_org_id") == workos_org_id:
            return o
    # Not found -> Create new
    name = "Org " + workos_org_id[-8:] if len(workos_org_id) > 8 else "New Org"
    return create_org(name=name, plan="free", owner_email=owner_email, workos_org_id=workos_org_id)


def get_org_by_email(email: str) -> Optional[dict]:
    """Part 204: Find org by owner_email (for JWT-authenticated users)."""
    if not email:
        return None
    email = email.strip().lower()
    for org in _load("orgs.json", {}).values():
        if (org.get("owner_email") or "").strip().lower() == email:
            return org
    return None


def migrate_orgs_paddle_field() -> int:
    """Part 204: Add paddle_customer_id='' to legacy orgs."""
    orgs = _load("orgs.json", {})
    changed = 0
    for o in orgs.values():
        if "paddle_customer_id" not in o:
            o["paddle_customer_id"] = ""
            changed += 1
    if changed:
        _save("orgs.json", orgs)
    return changed


def get_plan(plan_id: str) -> Optional[dict]:
    return _seed_plans().get(plan_id)

def create_plan(plan_id: str, data: dict) -> dict:
    plans = _seed_plans()
    if plan_id in plans:
        return plans[plan_id] # Or raise
    data["id"] = plan_id
    data["created_at"] = time.time()
    plans[plan_id] = data
    _save("plans.json", plans)
    return plans[plan_id]

def delete_plan(plan_id: str) -> bool:
    plans = _seed_plans()
    if plan_id in plans:
        del plans[plan_id]
        _save("plans.json", plans)
        return True
    return False


def get_org_by_paddle_customer(customer_id: str) -> Optional[dict]:
    """Part 209g: find org by paddle_customer_id (webhook fallback lookup)."""
    if not customer_id:
        return None
    for org in _load("orgs.json", {}).values():
        if org.get("paddle_customer_id") == customer_id:
            return org
    return None
