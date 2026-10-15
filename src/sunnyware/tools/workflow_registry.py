# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 122: named multi-step agent workflow registry.

Inspired by Bloomberg ASKB's reusable agentic workflows.

A workflow is an ordered list of steps:
    [{ "role": "actuary", "task": "...", "context": "optional" }, ...]

Running a workflow executes each step via orchestrator.run_agent,
collecting every result. Steps are sequential.

Storage: <data_root>/workflows/{name}.json
"""
import asyncio
import json
import re
import time
from pathlib import Path

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,63}$")
_MAX_STEPS = 20
_MAX_TASK_BYTES = 4096
_MAX_WORKFLOWS = 200
_STEP_TIMEOUT = 240.0  # per-step hard cap

# Prevent same-process recursive workflow execution.
_ACTIVE: set = set()


def _wf_dir() -> Path:
    from .. import paths
    d = paths.data_root() / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _wf_path(name: str) -> Path:
    d = _wf_dir()
    p = (d / (name + ".json")).resolve()
    if not str(p).startswith(str(d)):
        raise ValueError("invalid workflow name")
    return p


def _validate_name(name: str) -> str:
    n = (name or "").strip()
    if not _NAME_RE.match(n):
        raise ValueError(
            "invalid name: start with a letter, then letters/digits/_/- "
            "(max 64 chars)"
        )
    return n


def _validate_steps(raw_steps):
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("steps must be a non-empty list")
    if len(raw_steps) > _MAX_STEPS:
        raise ValueError("too many steps (max %d)" % _MAX_STEPS)
    out = []
    from .. import roles as _roles
    for i, s in enumerate(raw_steps):
        if not isinstance(s, dict):
            raise ValueError(f"steps[{i}] must be an object")
        role = (s.get("role") or "").strip().lower()
        task = (s.get("task") or "").strip()
        ctx = (s.get("context") or "").strip()
        if not role:
            raise ValueError(f"steps[{i}]: role is required")
        if not task:
            raise ValueError(f"steps[{i}]: task is required")
        if not _roles.is_valid(role):
            raise ValueError(
                f"steps[{i}]: unknown role '{role}' "
                f"(valid: {', '.join(_roles.role_names())})"
            )
        if len(task.encode("utf-8")) > _MAX_TASK_BYTES:
            raise ValueError(f"steps[{i}]: task too long (>4KB)")
        canon = _roles.canonical(role) or role
        entry = {"role": canon, "task": task}
        if ctx:
            entry["context"] = ctx
        out.append(entry)
    return out


def list_workflows():
    d = _wf_dir()
    out = []
    for p in sorted(d.glob("*.json"))[:_MAX_WORKFLOWS]:
        try:
            wf = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append({
            "name": p.stem,
            "description": wf.get("description", ""),
            "step_count": len(wf.get("steps") or []),
            "created_at": wf.get("created_at"),
            "last_run_at": wf.get("last_run_at"),
            "run_count": wf.get("run_count", 0),
            "last_status": wf.get("last_status"),
        })
    return out


def get_workflow(name: str):
    n = _validate_name(name)
    p = _wf_path(n)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_workflow(name, steps, description=""):
    n = _validate_name(name)
    valid_steps = _validate_steps(steps)
    p = _wf_path(n)
    prev = {}
    if p.exists():
        try:
            prev = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
    now = int(time.time())
    wf = {
        "name": n,
        "description": str(description or prev.get("description", "")),
        "steps": valid_steps,
        "created_at": prev.get("created_at") or now,
        "updated_at": now,
        "run_count": prev.get("run_count", 0),
        "last_status": prev.get("last_status"),
        "last_run_at": prev.get("last_run_at"),
    }
    p.write_text(json.dumps(wf, indent=2), encoding="utf-8")
    return wf


def delete_workflow(name: str) -> bool:
    n = _validate_name(name)
    p = _wf_path(n)
    if not p.exists():
        return False
    p.unlink()
    return True


class WorkflowRegistryTool:
    name = "workflow_registry"
    description = (
        "Named multi-step agent workflows. Save, list, get, run, or delete "
        "a workflow composed of sequential (role, task) steps. Running a "
        "workflow executes each step via the orchestrator with the "
        "specified role, collecting every result. Ideal for standardizing "
        "recurring analyses (e.g. 'quarterly_insurance_review')."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: list, save, get, run, delete",
            "required": True,
        },
        "name": {
            "type": "string",
            "description": "Workflow name (letter, then letters/digits/_/-)",
            "required": False,
        },
        "steps": {
            "type": "string",
            "description": "JSON array for action=save, e.g. '[{\"role\":\"actuary\",\"task\":\"...\"}]'",
            "required": False,
        },
        "description": {
            "type": "string",
            "description": "Short description (for action=save)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        from .. import roles as _roles
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required",
                    "available": ["list", "save", "get", "run", "delete"]}

        if action == "list":
            items = list_workflows()
            return {"count": len(items), "workflows": items}

        if action not in ("save", "get", "run", "delete"):
            return {"error": "unknown action '" + action + "'",
                    "available": ["list", "save", "get", "run", "delete"]}

        name = (args.get("name") or "").strip()
        if not name:
            return {"error": "name is required"}

        if action == "save":
            raw = args.get("steps")
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception as e:
                    return {"error": "steps is not valid JSON: " + str(e)}
            try:
                wf = save_workflow(name, raw, args.get("description") or "")
            except ValueError as e:
                return {"error": str(e)}
            return {"saved": True, "workflow": {
                "name": wf["name"],
                "description": wf["description"],
                "step_count": len(wf["steps"]),
                "steps": wf["steps"],
            }}

        if action == "get":
            try:
                wf = get_workflow(name)
            except ValueError as e:
                return {"error": str(e)}
            if wf is None:
                return {"error": "workflow not found: " + name}
            return wf

        if action == "delete":
            try:
                ok = delete_workflow(name)
            except ValueError as e:
                return {"error": str(e)}
            return {"deleted": ok, "name": name}

        if action == "run":
            try:
                wf = get_workflow(name)
            except ValueError as e:
                return {"error": str(e)}
            if wf is None:
                return {"error": "workflow not found: " + name}

            canonical = wf.get("name") or name
            if canonical in _ACTIVE:
                return {"error": "workflow already running: " + canonical}
            _ACTIVE.add(canonical)
            try:
                from .. import orchestrator as _orch
                results = []
                all_ok = True
                for i, step in enumerate(wf.get("steps") or []):
                    role = step.get("role")
                    task = step.get("task") or ""
                    ctx = step.get("context") or ""
                    prompt = task
                    if ctx:
                        prompt = task + "\n\n--- Context ---\n" + ctx
                    try:
                        res = await asyncio.wait_for(
                            _orch.run_agent(
                                prompt=prompt, role=role, session_uuid=None,
                            ),
                            timeout=_STEP_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        results.append({
                            "step": i, "role": role, "task": task,
                            "ok": False, "error": "step timed out",
                        })
                        all_ok = False
                        continue
                    except Exception as e:
                        results.append({
                            "step": i, "role": role, "task": task,
                            "ok": False,
                            "error": type(e).__name__ + ": " + str(e),
                        })
                        all_ok = False
                        continue
                    ok = bool((res or {}).get("ok"))
                    results.append({
                        "step": i,
                        "role": role,
                        "task": task,
                        "ok": ok,
                        "answer": (res or {}).get("answer", ""),
                        "iterations": (res or {}).get("iterations"),
                        "provider": (res or {}).get("provider"),
                    })
                    if not ok:
                        all_ok = False
            finally:
                _ACTIVE.discard(canonical)

            # Update metadata on the workflow file
            try:
                p = _wf_path(canonical)
                if p.exists():
                    meta = json.loads(p.read_text(encoding="utf-8"))
                    meta["run_count"] = meta.get("run_count", 0) + 1
                    meta["last_run_at"] = int(time.time())
                    meta["last_status"] = "ok" if all_ok else "error"
                    p.write_text(json.dumps(meta, indent=2),
                                 encoding="utf-8")
            except Exception:
                pass

            return {
                "name": canonical,
                "all_ok": all_ok,
                "step_count": len(results),
                "results": results,
            }

        return {"error": "unreachable"}
