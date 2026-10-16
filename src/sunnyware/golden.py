# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 158: golden dataset regression framework.

A golden dataset is a curated set of {input -> expected_output} pairs
frozen at a point in time. Running the suite against the CURRENT agent
tells you if behavior has drifted from that baseline.

This is deliberately SEPARATE from evals.py:
  evals.py  : quality assertions (does the answer contain X? pass/fail)
  golden.py : regression baseline (does the answer still match what
              we captured last time? exact/contains-list/similarity)

Env vars:
  SUNNYWARE_GOLDEN_FILE       path to JSON dataset (default: static/)
  SUNNYWARE_GOLDEN_STORAGE    path to run-history JSON (/data/)
  SUNNYWARE_GOLDEN_KEEP_RUNS  max runs retained (default 30)

Match modes per case:
  exact        - response.strip() == expected.strip()
  contains     - all entries in expected_list appear in response
  not_contains - none of the entries appear in response
  regex        - re.search(pattern, response)
  min_length   - len(response) >= value
"""

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Optional

VERSION = 1


def _static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


def _default_file() -> Path:
    env = os.getenv("SUNNYWARE_GOLDEN_FILE")
    if env:
        return Path(env)
    return _static_dir() / "golden_dataset.json"


def _storage_path() -> Path:
    env = os.getenv("SUNNYWARE_GOLDEN_STORAGE")
    if env:
        return Path(env)
    data = Path("/data")
    if data.is_dir():
        return data / "golden_runs.json"
    return Path("golden_runs.json")


def load_cases() -> list:
    try:
        p = _default_file()
        if not p.exists():
            return []
        with p.open(encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d = d.get("cases") or []
        if not isinstance(d, list):
            return []
        out = []
        for c in d:
            if not isinstance(c, dict):
                continue
            if not c.get("id") or "input" not in c:
                continue
            c.setdefault("name", c["id"])
            c.setdefault("match", "contains")
            c.setdefault("expected", [])
            c.setdefault("tags", [])
            c.setdefault("weight", 1.0)
            c.setdefault("timeout_sec", 30)
            out.append(c)
        return out
    except Exception:
        return []


def save_cases(cases: list) -> bool:
    try:
        p = _default_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump({"version": VERSION, "cases": cases}, f, indent=2)
        tmp.replace(p)
        return True
    except Exception:
        return False


def load_history() -> dict:
    try:
        p = _storage_path()
        if not p.exists():
            return {"version": VERSION, "runs": []}
        with p.open(encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return {"version": VERSION, "runs": []}
        d.setdefault("version", VERSION)
        if not isinstance(d.get("runs"), list):
            d["runs"] = []
        return d
    except Exception:
        return {"version": VERSION, "runs": []}


def save_history(h: dict) -> None:
    try:
        p = _storage_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(h, f, indent=2)
        tmp.replace(p)
    except Exception:
        pass


def prune_history(keep: Optional[int] = None) -> int:
    if keep is None:
        try:
            keep = int(os.getenv("SUNNYWARE_GOLDEN_KEEP_RUNS", "30") or "30")
        except Exception:
            keep = 30
    h = load_history()
    runs = h.get("runs") or []
    if len(runs) <= keep:
        return 0
    removed = len(runs) - keep
    h["runs"] = runs[-keep:]
    save_history(h)
    return removed


def _norm(s) -> str:
    if s is None:
        return ""
    return str(s).strip()


def compare(response: str, expected, match: str) -> dict:
    """Return {ok: bool, detail: str}. Never raises."""
    r = _norm(response)
    m = (match or "contains").lower()
    try:
        if m == "exact":
            e = _norm(expected)
            ok = r == e
            return {"ok": ok, "detail": f"len={len(r)} vs {len(e)}"}
        if m == "contains":
            items = expected if isinstance(expected, list) else [expected]
            missing = [str(i) for i in items if str(i) not in r]
            return {"ok": not missing, "detail": f"missing={missing[:5]}"}
        if m == "not_contains":
            items = expected if isinstance(expected, list) else [expected]
            found = [str(i) for i in items if str(i) in r]
            return {"ok": not found, "detail": f"found={found[:5]}"}
        if m == "regex":
            pattern = str(expected if not isinstance(expected, list)
                          else (expected[0] if expected else ""))
            ok = bool(re.search(pattern, r))
            return {"ok": ok, "detail": f"pattern={pattern[:40]!r}"}
        if m == "min_length":
            val = int(expected if not isinstance(expected, list)
                      else (expected[0] if expected else 0))
            return {"ok": len(r) >= val, "detail": f"len={len(r)} vs {val}"}
        return {"ok": False, "detail": f"unknown_match:{m}"}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}


async def run_case(case: dict, call_fn) -> dict:
    """Run one case against call_fn. Never raises."""
    cid = case.get("id", "?")
    name = case.get("name", cid)
    inp = case.get("input", "")
    expected = case.get("expected", [])
    match = case.get("match", "contains")
    timeout = float(case.get("timeout_sec") or 30)

    t0 = time.time()
    response = ""
    error = None
    try:
        import asyncio
        out = call_fn(inp)
        if hasattr(out, "__await__"):
            out = await asyncio.wait_for(out, timeout=timeout)
        response = out if isinstance(out, str) else str(out)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    duration_ms = int((time.time() - t0) * 1000)

    if error:
        return {
            "case_id": cid, "name": name, "status": "error",
            "duration_ms": duration_ms,
            "response_excerpt": "", "match_detail": error,
        }

    cmp = compare(response, expected, match)
    return {
        "case_id": cid, "name": name,
        "status": "pass" if cmp["ok"] else "fail",
        "duration_ms": duration_ms,
        "response_excerpt": response[:400],
        "match_detail": cmp["detail"],
        "match_mode": match,
    }


async def run_suite(call_fn, *, tags: Optional[list] = None,
                    triggered_by: str = "manual") -> dict:
    """Run the golden suite. Persist to history. Never raises."""
    t0 = time.time()
    all_cases = load_cases()
    if tags:
        ts = set(tags)
        cases = [c for c in all_cases if ts & set(c.get("tags") or [])]
    else:
        cases = list(all_cases)

    run_id = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(t0))}-{uuid.uuid4().hex[:6]}"
    case_results = []
    passed = failed = errored = 0
    weighted_sum = 0.0
    weight_total = 0.0

    for c in cases:
        try:
            r = await run_case(c, call_fn)
        except Exception as e:
            r = {
                "case_id": c.get("id", "?"), "name": c.get("name", ""),
                "status": "error", "duration_ms": 0,
                "response_excerpt": "",
                "match_detail": f"{type(e).__name__}: {e}",
            }
        case_results.append(r)
        w = float(c.get("weight") or 1.0)
        weight_total += w
        if r["status"] == "pass":
            passed += 1
            weighted_sum += w
        elif r["status"] == "fail":
            failed += 1
        else:
            errored += 1

    t_end = time.time()
    total = len(case_results)
    score = round(weighted_sum / weight_total, 4) if weight_total > 0 else 0.0

    run = {
        "run_id": run_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_end)),
        "duration_ms": int((t_end - t0) * 1000),
        "triggered_by": triggered_by,
        "tags": list(tags) if tags else None,
        "cases": case_results,
        "summary": {
            "total": total, "passed": passed,
            "failed": failed, "errors": errored,
            "score": score,
        },
    }
    h = load_history()
    h.setdefault("runs", []).append(run)
    save_history(h)
    prune_history()
    return run


def latest_run() -> Optional[dict]:
    runs = load_history().get("runs") or []
    return runs[-1] if runs else None


def trends(n: int = 10) -> list:
    runs = load_history().get("runs") or []
    out = []
    for r in runs[-max(1, n):]:
        out.append({
            "run_id": r.get("run_id"),
            "started_at": r.get("started_at"),
            "triggered_by": r.get("triggered_by"),
            "summary": r.get("summary"),
        })
    return out


def promote(case_dict: dict) -> dict:
    """Add or update a golden case in the dataset file."""
    if not isinstance(case_dict, dict) or not case_dict.get("id"):
        return {"ok": False, "error": "id required"}
    if "input" not in case_dict:
        return {"ok": False, "error": "input required"}
    cases = load_cases()
    idx = None
    for i, c in enumerate(cases):
        if c.get("id") == case_dict["id"]:
            idx = i
            break
    case_dict.setdefault("match", "contains")
    case_dict.setdefault("expected", [])
    case_dict.setdefault("tags", [])
    case_dict.setdefault("weight", 1.0)
    case_dict.setdefault("timeout_sec", 30)
    case_dict.setdefault("name", case_dict["id"])
    if idx is None:
        cases.append(case_dict)
        action = "created"
    else:
        cases[idx] = case_dict
        action = "updated"
    ok = save_cases(cases)
    return {"ok": ok, "action": action,
            "case_id": case_dict["id"], "total": len(cases)}


def delete_case(case_id: str) -> dict:
    cases = load_cases()
    before = len(cases)
    cases = [c for c in cases if c.get("id") != case_id]
    if len(cases) == before:
        return {"ok": False, "error": "not_found"}
    save_cases(cases)
    return {"ok": True, "deleted": case_id, "total": len(cases)}


def status() -> dict:
    cases = load_cases()
    runs = load_history().get("runs") or []
    last = runs[-1] if runs else None
    tag_counts = {}
    for c in cases:
        for t in c.get("tags") or []:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    return {
        "version": VERSION,
        "case_count": len(cases),
        "case_tags": tag_counts,
        "stored_runs": len(runs),
        "dataset_path": str(_default_file()),
        "storage_path": str(_storage_path()),
        "last_run": ({
            "run_id": last.get("run_id"),
            "started_at": last.get("started_at"),
            "summary": last.get("summary"),
            "triggered_by": last.get("triggered_by"),
        } if last else None),
    }


async def default_call_fn(text: str) -> str:
    """Best-effort orchestrator wrapper (mirrors evals.default_call_fn)."""
    from . import orchestrator as _orc
    for name in ("run", "run_prompt", "run_agent"):
        fn = getattr(_orc, name, None)
        if not callable(fn):
            continue
        try:
            out = fn(text)
            if hasattr(out, "__await__"):
                out = await out
        except TypeError:
            continue
        if isinstance(out, dict):
            for k in ("answer", "response", "output", "text", "content"):
                v = out.get(k)
                if isinstance(v, str):
                    return v
            return json.dumps(out, default=str)
        return str(out)
    raise RuntimeError("no orchestrator entrypoint")


async def dry_run_call_fn(text: str) -> str:
    """Deterministic responses for framework testing."""
    t = (text or "").lower()
    if "pong" in t:
        return "pong"
    if "2+2" in t or "2 + 2" in t:
        return "4"
    if "hello" in t:
        return "hello there"
    return f"__dry_run__: {text[:60]}"
