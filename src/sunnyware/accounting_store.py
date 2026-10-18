# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 188: Financial / Accounting data store (Ledgerly integration).

Self-contained financial model inspired by Ledgerly:
- Customers, Plans (extended), Invoices, Ledger
- Costs, Capital, Compliance, Coupons, Dunning
- Entitlements, Usage, Audit log, Monthly history
"""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional


def _path() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data / "accounting.json"
    return Path("data") / "accounting.json"


def _default() -> dict:
    return {
        "co": "Sunnyware",
        "sym": "$",
        "start": time.strftime("%Y-%m"),
        "tax": 18,
        "itx": 21,
        "thr": {"gm": 70, "ai": 30},
        "cats": ["Payroll", "Hosting", "AI API", "Software", "Domain",
                 "Marketing", "Legal", "Accounting", "Equipment", "Other"],
        "bud": {},
        "feat": [
            {"k": "api", "n": "API access", "t": "b"},
            {"k": "sso", "n": "SSO", "t": "b"},
            {"k": "audit", "n": "Audit logs", "t": "b"},
            {"k": "seats", "n": "Seats", "t": "n"},
            {"k": "rate", "n": "API calls / min", "t": "n"},
        ],
        "cust": [],   # [{id, name, plan, st}]
        "plans": [],  # [{id, name, price, tokens, trial, disc}]
        "inv": [],    # [{no, c, amt, tax, st, cp}]
        "led": [],    # [{d, t, desc, amt}]
        "mo": [],     # [{m, r, c}]
        "costs": [],  # [{id, name, cat, amt, f, s, life}]
        "cap": [],    # [{id, d, t, name, amt, r}]
        "comp": [],   # [{id, name, area, f, due}]
        "coup": [],   # [{code, type, val, plans, max, used, exp, on}]
        "dun": [],    # [{c, amt, why, st}]
        "ent": {},    # {plan_id: {feat_key: value}}
        "use": {},    # {cust_id: {tr, lg, f, tk}}
        "audit": [],  # [{t, u, a}]
    }


_CACHE = {"mtime": 0.0, "state": None}


def _load() -> dict:
    p = _path()
    if not p.exists():
        return _default()
    try:
        mtime = p.stat().st_mtime
        if _CACHE["state"] and mtime == _CACHE["mtime"]:
            return _CACHE["state"]
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = _default()
        _CACHE["mtime"] = mtime
        _CACHE["state"] = data
        return data
    except Exception:
        return _default()


def _save(state: dict) -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True),
                       encoding="utf-8")
        tmp.replace(p)
        _CACHE["mtime"] = p.stat().st_mtime
        _CACHE["state"] = state
    except Exception:
        pass


def _next_id(arr: list) -> int:
    return max([x.get("id", 0) for x in arr] + [0]) + 1


# ─── Full State ───
def get_state() -> dict:
    return _load()


def set_state(state: dict) -> dict:
    _save(state)
    return state


def reset_empty() -> dict:
    s = _default()
    _save(s)
    return s


# ─── Customers ───
def list_customers() -> list:
    return _load().get("cust", [])


def create_customer(name: str, plan_id: str, status: str = "trial") -> dict:
    s = _load()
    cid = _next_id(s["cust"])
    cust = {"id": cid, "name": name, "plan": plan_id, "st": status}
    s["cust"].append(cust)
    _save(s)
    return cust


def update_customer(cid: int, patch: dict) -> Optional[dict]:
    s = _load()
    for c in s["cust"]:
        if c.get("id") == cid:
            c.update(patch)
            _save(s)
            return c
    return None


def delete_customer(cid: int) -> bool:
    s = _load()
    s["cust"] = [c for c in s["cust"] if c.get("id") != cid]
    _save(s)
    return True


# ─── Plans ───
def list_plans() -> list:
    return _load().get("plans", [])


def upsert_plan(data: dict) -> dict:
    s = _load()
    if not data.get("id"):
        data["id"] = "p" + secrets.token_hex(4)
    for i, p in enumerate(s["plans"]):
        if p.get("id") == data["id"]:
            s["plans"][i] = data
            _save(s)
            return data
    s["plans"].append(data)
    _save(s)
    return data


def delete_plan(plan_id: str) -> bool:
    s = _load()
    if any(c.get("plan") == plan_id for c in s["cust"]):
        return False
    s["plans"] = [p for p in s["plans"] if p.get("id") != plan_id]
    _save(s)
    return True


# ─── Invoices ───
def list_invoices() -> list:
    return _load().get("inv", [])


def create_invoice(customer_id: int, amount: float, tax: float,
                   status: str = "due", coupon: str = "") -> dict:
    s = _load()
    n = 1001 + len(s["inv"])
    inv = {"no": f"INV-{n}", "c": customer_id, "amt": amount,
           "tax": tax, "st": status, "cp": coupon}
    s["inv"].append(inv)
    _save(s)
    return inv


def mark_invoice_paid(inv_no: str) -> Optional[dict]:
    s = _load()
    for v in s["inv"]:
        if v["no"] == inv_no and v["st"] == "due":
            v["st"] = "paid"
            total = v["amt"] * (1 + v["tax"] / 100)
            s["led"].append({
                "d": time.strftime("%Y-%m-%d"),
                "t": "Revenue",
                "desc": f"{v['no']} paid",
                "amt": round(total, 2),
            })
            _save(s)
            return v
    return None


def refund_invoice(inv_no: str) -> Optional[dict]:
    s = _load()
    for v in s["inv"]:
        if v["no"] == inv_no and v["st"] == "paid":
            v["st"] = "refunded"
            total = v["amt"] * (1 + v["tax"] / 100)
            s["led"].append({
                "d": time.strftime("%Y-%m-%d"),
                "t": "Revenue",
                "desc": f"{v['no']} refunded",
                "amt": -round(total, 2),
            })
            _save(s)
            return v
    return None


# ─── Ledger ───
def list_ledger() -> list:
    return _load().get("led", [])


def add_ledger_entry(etype: str, desc: str, amount: float) -> dict:
    s = _load()
    entry = {
        "d": time.strftime("%Y-%m-%d"),
        "t": etype,
        "desc": desc,
        "amt": amount,
    }
    s["led"].append(entry)
    _save(s)
    return entry


# ─── Costs ───
def list_costs() -> list:
    return _load().get("costs", [])


def create_cost(name: str, cat: str, amount: float,
                freq: str = "month", start: str = "",
                life: int = 0) -> dict:
    s = _load()
    cid = _next_id(s["costs"])
    cost = {
        "id": cid, "name": name, "cat": cat, "amt": amount,
        "f": freq, "s": start or time.strftime("%Y-%m"), "life": life,
    }
    s["costs"].append(cost)
    _save(s)
    return cost


def delete_cost(cid: int) -> bool:
    s = _load()
    s["costs"] = [c for c in s["costs"] if c.get("id") != cid]
    _save(s)
    return True


# ─── Capital ───
def list_capital() -> list:
    return _load().get("cap", [])


def create_capital(ctype: str, name: str, amount: float,
                   date: str = "", rate: float = 0) -> dict:
    s = _load()
    cid = _next_id(s["cap"])
    cap = {
        "id": cid, "d": date or time.strftime("%Y-%m-%d"),
        "t": ctype, "name": name, "amt": amount, "r": rate,
    }
    s["cap"].append(cap)
    _save(s)
    return cap


def delete_capital(cid: int) -> bool:
    s = _load()
    s["cap"] = [c for c in s["cap"] if c.get("id") != cid]
    _save(s)
    return True


# ─── Compliance ───
def list_compliance() -> list:
    return _load().get("comp", [])


def create_compliance(name: str, area: str, freq: str,
                     due: str) -> dict:
    s = _load()
    cid = _next_id(s["comp"])
    comp = {"id": cid, "name": name, "area": area, "f": freq, "due": due}
    s["comp"].append(comp)
    _save(s)
    return comp


def delete_compliance(cid: int) -> bool:
    s = _load()
    s["comp"] = [c for c in s["comp"] if c.get("id") != cid]
    _save(s)
    return True


def mark_compliance_filed(cid: int) -> Optional[dict]:
    s = _load()
    for c in s["comp"]:
        if c.get("id") == cid:
            months = {"month": 1, "quarter": 3, "year": 12}.get(c.get("f", "year"), 12)
            try:
                from datetime import datetime, timedelta
                dt = datetime.strptime(c["due"], "%Y-%m-%d")
                dt = dt + timedelta(days=months * 30)
                c["due"] = dt.strftime("%Y-%m-%d")
            except Exception:
                pass
            _save(s)
            return c
    return None


# ─── Coupons ───
def list_coupons() -> list:
    return _load().get("coup", [])


def create_coupon(code: str, ctype: str, val: float,
                  plans: list, max_uses: int = 0,
                  exp: str = "") -> dict:
    s = _load()
    coup = {
        "code": code.upper(), "type": ctype, "val": val,
        "plans": plans, "max": max_uses, "used": 0,
        "exp": exp, "on": True,
    }
    s["coup"].append(coup)
    _save(s)
    return coup


def toggle_coupon(code: str) -> Optional[dict]:
    s = _load()
    for c in s["coup"]:
        if c["code"] == code.upper():
            c["on"] = not c.get("on", True)
            _save(s)
            return c
    return None


def delete_coupon(code: str) -> bool:
    s = _load()
    s["coup"] = [c for c in s["coup"] if c["code"] != code.upper()]
    _save(s)
    return True


# ─── Dunning ───
def list_dunning() -> list:
    return _load().get("dun", [])


def advance_dunning(idx: int) -> Optional[dict]:
    s = _load()
    if 0 <= idx < len(s["dun"]):
        d = s["dun"][idx]
        d["st"] = min(4, d.get("st", 1) + 1)
        _save(s)
        return d
    return None


def retry_dunning(idx: int) -> Optional[dict]:
    import random
    s = _load()
    if 0 <= idx < len(s["dun"]):
        d = s["dun"][idx]
        if random.random() < 0.5:
            s["led"].append({
                "d": time.strftime("%Y-%m-%d"),
                "t": "Revenue",
                "desc": "Recovered via Paddle",
                "amt": d["amt"],
            })
            s["dun"].pop(idx)
            _save(s)
            return {"recovered": True, "amount": d["amt"]}
        d["st"] = min(4, d.get("st", 1) + 1)
        _save(s)
        return {"recovered": False}
    return None


# ─── Entitlements & Usage ───
def get_entitlements() -> dict:
    return _load().get("ent", {})


def set_entitlement(plan_id: str, feat_key: str, value) -> bool:
    s = _load()
    s.setdefault("ent", {}).setdefault(plan_id, {})[feat_key] = value
    _save(s)
    return True


def get_usage() -> dict:
    return _load().get("use", {})


def set_usage(customer_id: int, data: dict) -> bool:
    s = _load()
    s.setdefault("use", {})[str(customer_id)] = data
    _save(s)
    return True


# ─── Audit ───
def list_audit() -> list:
    return _load().get("audit", [])


def add_audit(user: str, action: str) -> bool:
    s = _load()
    s["audit"].append({
        "t": time.strftime("%H:%M"),
        "u": user,
        "a": action,
    })
    if len(s["audit"]) > 500:
        s["audit"] = s["audit"][-500:]
    _save(s)
    return True


# ─── Monthly History ───
def list_monthly() -> list:
    return _load().get("mo", [])


def set_monthly(month: str, revenue: float, cost: float) -> bool:
    s = _load()
    for m in s["mo"]:
        if m["m"] == month:
            m["r"] = revenue
            m["c"] = cost
            _save(s)
            return True
    s["mo"].append({"m": month, "r": revenue, "c": cost})
    _save(s)
    return True


# ─── Settings ───
def update_settings(patch: dict) -> dict:
    s = _load()
    for k in ["co", "sym", "start", "tax", "itx", "thr", "bud", "cats"]:
        if k in patch:
            s[k] = patch[k]
    _save(s)
    return s


# ─── Calculations ───
def _this_month() -> str:
    return time.strftime("%Y-%m")


def _sum_ledger(etype: str, month: str) -> float:
    s = _load()
    return sum(l["amt"] for l in s["led"]
               if l["t"] == etype and l["d"].startswith(month))


def dashboard() -> dict:
    s = _load()
    plans = {p["id"]: p for p in s["plans"]}
    mrr = sum(plans.get(c.get("plan"), {}).get("price", 0)
              for c in s["cust"] if c.get("st") == "active")

    rev = _sum_ledger("Revenue", _this_month())
    fee = -_sum_ledger("Fee", _this_month())
    ai = -_sum_ledger("AI cost", _this_month())
    exp = -_sum_ledger("Expense", _this_month())

    return {
        "mrr": mrr,
        "arr": mrr * 12,
        "revenue": rev,
        "fee": fee,
        "ai_cost": ai,
        "expenses": exp,
        "gross_margin": ((rev - ai - fee) / rev * 100) if rev else 0,
        "net": rev - fee - ai - exp,
    }


def pnl() -> dict:
    s = _load()
    m = _this_month()
    rev = _sum_ledger("Revenue", m)
    fee = -_sum_ledger("Fee", m)
    ai = -_sum_ledger("AI cost", m)
    exp = -_sum_ledger("Expense", m)
    tax = sum(v["amt"] * v["tax"] / 100 for v in s["inv"] if v["st"] == "paid")
    return {
        "revenue": rev,
        "fee": fee,
        "ai_cost": ai,
        "expenses": exp,
        "net": rev - fee - ai - exp,
        "tax_collected": tax,
    }


# ─── Sync from saas_store ───
def sync_from_saas() -> bool:
    try:
        from . import saas_store as _saas
        s = _load()
        if not s["plans"]:
            for p in _saas.list_plans():
                s["plans"].append({
                    "id": p["id"], "name": p["name"],
                    "price": p.get("price_monthly", 0),
                    "tokens": 5, "trial": 0, "disc": 15,
                })
        if not s["cust"]:
            for o in _saas.list_orgs():
                s["cust"].append({
                    "id": len(s["cust"]) + 1,
                    "name": o.get("name", "Org"),
                    "plan": o.get("plan", "free"),
                    "st": "active" if o.get("status") == "active" else "churned",
                })
        _save(s)
        return True
    except Exception:
        return False
