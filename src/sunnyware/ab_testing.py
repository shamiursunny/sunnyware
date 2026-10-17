# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 169: prompt A/B testing.

Deterministic per-(session, experiment) assignment so the same user
always gets the same arm. No live experiment: pick_variant returns
(None, None) and orchestrator is a no-op.

Assignment algorithm:
  bucket = sha256(session_id + exp_id) mod 100
  bucket < split_pct  -> arm "a" (control, no extra text)
  bucket >= split_pct -> arm "b" (variant, prepends prompt_b_extra)

Storage:
  SUNNYWARE_AB_STORAGE override, else /data/ab_experiments.json on
  HF, else data/ab_experiments.json. Same pattern as golden.py.

Public API:
  create(name, role, split_pct, prompt_b_extra, active) -> dict
  list_all() -> {"experiments": [...]}
  results(exp_id) -> {"experiment": {...}, "assignments": {...}}
  delete(exp_id) -> {"ok": bool, "id": str}
  pick_variant(session_id, role) -> (arm|None, extra_text|None)

Config:
  SUNNYWARE_AB_ENABLED=1         master switch (default on)
  SUNNYWARE_AB_STORAGE=<path>    override storage file
"""

import hashlib
import json
import os
import time
import uuid
from pathlib import Path


_DEFAULT_STATE = {
    "experiments": [],
    "assignments": {},
    "recent": [],
}


def _enabled() -> bool:
    v = (os.getenv("SUNNYWARE_AB_ENABLED", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def _path() -> Path:
    env = os.getenv("SUNNYWARE_AB_STORAGE")
    if env:
        return Path(env)
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data / "ab_experiments.json"
    return Path("data") / "ab_experiments.json"


def _load() -> dict:
    p = _path()
    if not p.exists():
        return dict(_DEFAULT_STATE)
    try:
        raw = p.read_text(encoding="utf-8")
        d = json.loads(raw)
    except Exception:
        return dict(_DEFAULT_STATE)
    if not isinstance(d, dict):
        return dict(_DEFAULT_STATE)
    for k, v in _DEFAULT_STATE.items():
        if k not in d or not isinstance(d[k], type(v)):
            d[k] = v.copy() if hasattr(v, "copy") else v
    return d


def _save(state: dict) -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2, default=str),
                     encoding="utf-8")
    except Exception:
        pass


def _bucket(session_id: str, exp_id: str) -> int:
    h = hashlib.sha256((str(session_id) + "|" + str(exp_id))
                       .encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100


def create(name, role="*", split_pct=50, prompt_b_extra="",
           active=True):
    """Create a new experiment. Returns {ok, experiment}."""
    if not name:
        return {"ok": False, "error": "name required"}
    try:
        split_pct = max(0, min(100, int(split_pct)))
    except Exception:
        split_pct = 50

    state = _load()
    exp = {
        "id": uuid.uuid4().hex[:12],
        "name": str(name)[:80],
        "role": str(role or "*")[:40],
        "split_pct": split_pct,
        "prompt_b_extra": str(prompt_b_extra or "")[:8000],
        "active": bool(active),
        "created_at": time.time(),
    }
    state["experiments"].append(exp)
    state["assignments"][exp["id"]] = {"a": 0, "b": 0}
    _save(state)
    return {"ok": True, "experiment": exp}


def list_all():
    state = _load()
    return {"experiments": list(state.get("experiments") or []),
            "path": str(_path())}


def results(exp_id):
    state = _load()
    exps = state.get("experiments") or []
    exp = next((e for e in exps if e.get("id") == exp_id), None)
    if not exp:
        return {"ok": False, "error": "not_found", "id": exp_id}
    counts = (state.get("assignments") or {}).get(exp_id, {"a": 0, "b": 0})
    total = counts.get("a", 0) + counts.get("b", 0)
    return {
        "ok": True,
        "experiment": exp,
        "assignments": counts,
        "total_assignments": total,
        "recent": [r for r in (state.get("recent") or [])
                   if r.get("exp_id") == exp_id][-20:],
    }


def delete(exp_id):
    state = _load()
    before = len(state.get("experiments") or [])
    state["experiments"] = [
        e for e in (state.get("experiments") or [])
        if e.get("id") != exp_id
    ]
    state.get("assignments", {}).pop(exp_id, None)
    state["recent"] = [
        r for r in (state.get("recent") or [])
        if r.get("exp_id") != exp_id
    ]
    after = len(state["experiments"])
    _save(state)
    return {"ok": before != after, "id": exp_id}


def pick_variant(session_id, role):
    """Return (arm, extra_text).

    arm is "a" (control), "b" (variant), or None (no experiment matched).
    extra_text is only non-empty for arm "b".
    """
    if not _enabled():
        return None, None
    role = str(role or "")
    session_id = str(session_id or "")

    state = _load()
    exps = state.get("experiments") or []
    for exp in exps:
        if not exp.get("active"):
            continue
        exp_role = exp.get("role") or "*"
        if exp_role != "*" and exp_role != role:
            continue
        bucket = _bucket(session_id, exp.get("id", ""))
        split = int(exp.get("split_pct", 50))
        arm = "b" if bucket >= split else "a"
        # Track
        state["assignments"].setdefault(
            exp["id"], {"a": 0, "b": 0}
        )[arm] = state["assignments"].setdefault(
            exp["id"], {"a": 0, "b": 0}
        ).get(arm, 0) + 1
        state["recent"] = (state.get("recent") or [])[-99:] + [{
            "ts": time.time(),
            "exp_id": exp["id"],
            "session": session_id[:40],
            "role": role,
            "arm": arm,
        }]
        _save(state)
        if arm == "b":
            return "b", exp.get("prompt_b_extra") or ""
        return "a", None
    return None, None


def enabled() -> bool:
    return _enabled()


def reset():
    """Clear all experiments. Only for smoke tests."""
    _save(dict(_DEFAULT_STATE))
