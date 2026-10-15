# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 120: reusable script registry.

Store, list, and re-run named Python scripts produced by the agent.
Inspired by Bloomberg's BQL save-as-script workflow.

Scripts live in <data_root>/scripts/. Each script has:
  - <name>.py        : the source
  - <name>.meta.json : description, created_at, run_count, last_status
"""
import json
import re
import time
from pathlib import Path


_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,63}$")
_MAX_CODE_BYTES = 64 * 1024
_MAX_SCRIPTS = 500


def _scripts_dir() -> Path:
    from .. import paths
    d = paths.data_root() / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _script_path(name: str) -> Path:
    d = _scripts_dir()
    p = (d / (name + ".py")).resolve()
    if not str(p).startswith(str(d)):
        raise ValueError("invalid script name")
    return p


def _meta_path(name: str) -> Path:
    return _script_path(name).with_suffix(".meta.json")


def _validate_name(name: str) -> str:
    n = (name or "").strip()
    if not _NAME_RE.match(n):
        raise ValueError(
            "invalid name: must start with a letter, then letters/"
            "digits/_/- (max 64 chars)"
        )
    return n


def list_scripts():
    d = _scripts_dir()
    out = []
    for p in sorted(d.glob("*.py"))[:_MAX_SCRIPTS]:
        name = p.stem
        meta = {}
        mp = p.with_suffix(".meta.json")
        try:
            if mp.exists():
                meta = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        try:
            size = p.stat().st_size
        except Exception:
            size = None
        out.append({
            "name": name,
            "size_bytes": size,
            "description": meta.get("description", ""),
            "created_at": meta.get("created_at"),
            "last_run_at": meta.get("last_run_at"),
            "run_count": meta.get("run_count", 0),
            "last_status": meta.get("last_status"),
        })
    return out


def save_script_internal(name: str, code: str, description: str = ""):
    n = _validate_name(name)
    src = str(code or "")
    if len(src.encode("utf-8")) > _MAX_CODE_BYTES:
        raise ValueError("code too long")
    p = _script_path(n)
    p.write_text(src, encoding="utf-8")
    mp = _meta_path(n)
    prev = {}
    try:
        if mp.exists():
            prev = json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        prev = {}
    now = int(time.time())
    meta = {
        "name": n,
        "description": str(description or prev.get("description", "")),
        "created_at": prev.get("created_at") or now,
        "updated_at": now,
        "run_count": prev.get("run_count", 0),
        "last_status": prev.get("last_status"),
        "last_run_at": prev.get("last_run_at"),
    }
    mp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def get_script(name: str):
    n = _validate_name(name)
    p = _script_path(n)
    if not p.exists():
        return None
    meta = {}
    mp = _meta_path(n)
    try:
        if mp.exists():
            meta = json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    return {"name": n, "code": p.read_text(encoding="utf-8"), "meta": meta}


def delete_script(name: str) -> bool:
    n = _validate_name(name)
    p = _script_path(n)
    if not p.exists():
        return False
    p.unlink()
    mp = _meta_path(n)
    if mp.exists():
        mp.unlink()
    return True


class ScriptRegistryTool:
    name = "script_registry"
    description = (
        "Named Python script registry. Save, list, get, run, or delete "
        "reusable scripts. Every script is sandbox-validated on run, "
        "executed via the same engine as python_eval. Use this to "
        "standardize recurring analyses."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: list, save, get, run, delete",
            "required": True,
        },
        "name": {
            "type": "string",
            "description": "Script name (letter, then letters/digits/_/-)",
            "required": False,
        },
        "code": {
            "type": "string",
            "description": "Source code (for action=save)",
            "required": False,
        },
        "description": {
            "type": "string",
            "description": "Short description (for action=save)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        import asyncio
        from . import _sandbox
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required",
                    "available": ["list", "save", "get", "run", "delete"]}

        if action == "list":
            items = list_scripts()
            return {"count": len(items), "scripts": items}

        if action not in ("save", "get", "run", "delete"):
            return {"error": "unknown action '" + action + "'",
                    "available": ["list", "save", "get", "run", "delete"]}

        name = (args.get("name") or "").strip()
        if not name:
            return {"error": "name is required"}

        if action == "save":
            code = str(args.get("code") or "")
            if not code:
                return {"error": "code is required"}
            errs = _sandbox.validate(code)
            if errs:
                return {"error": "code rejected", "reasons": errs}
            try:
                meta = save_script_internal(name, code,
                                            args.get("description") or "")
            except ValueError as e:
                return {"error": str(e)}
            return {"saved": True, "meta": meta}

        if action == "get":
            try:
                got = get_script(name)
            except ValueError as e:
                return {"error": str(e)}
            if got is None:
                return {"error": "script not found: " + name}
            return got

        if action == "delete":
            try:
                ok = delete_script(name)
            except ValueError as e:
                return {"error": str(e)}
            return {"deleted": ok, "name": name}

        if action == "run":
            try:
                got = get_script(name)
            except ValueError as e:
                return {"error": str(e)}
            if got is None:
                return {"error": "script not found: " + name}
            code = got["code"]
            errs = _sandbox.validate(code)
            if errs:
                return {"error": "code rejected", "reasons": errs}
            g = _sandbox.build_globals()
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_sandbox.exec_code, code, g),
                    timeout=_sandbox.DEFAULT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return {"error": "execution timed out"}
            chart = _sandbox.capture_chart(g.get("plt"))
            if chart:
                result.update(chart)
            try:
                mp = _meta_path(name)
                meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
                meta["run_count"] = meta.get("run_count", 0) + 1
                meta["last_run_at"] = int(time.time())
                meta["last_status"] = "ok" if not result.get("error") else "error"
                mp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            except Exception:
                pass
            return {"name": name, "result": result}

        return {"error": "unknown action '" + action + "'",
                "available": ["list", "save", "get", "run", "delete"]}
