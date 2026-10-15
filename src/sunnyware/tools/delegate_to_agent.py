# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 114: agent-to-agent delegation tool.

Enables hierarchical delegation: CFO -> CDO -> workers.
Strictly bounded:
  - context vars track current role, depth, and path
  - max depth 3 (CFO -> CDO -> worker)
  - cycle detection by delegation path
  - permissions enforced via roles._DELEGATION_MATRIX
  - sub-agent uses its own role prompt + tool subset
  - sub-agent runs are synchronous (awaited) with no on_event
"""
import contextvars
from typing import List, Tuple

# ── Delegation state (safe across async awaits) ─────────────
_CURRENT_ROLE = contextvars.ContextVar("sunnyware_role", default="general")
_DELEGATION_DEPTH = contextvars.ContextVar("sunnyware_depth", default=0)
_DELEGATION_PATH = contextvars.ContextVar("sunnyware_path", default=())

_MAX_DEPTH = 3
_SUB_AGENT_TIMEOUT = 120.0   # per sub-agent wall clock


def get_current_role() -> str:
    return _CURRENT_ROLE.get()


def get_depth() -> int:
    return _DELEGATION_DEPTH.get()


def get_path() -> List[str]:
    return list(_DELEGATION_PATH.get())


class DelegateToAgentTool:
    name = "delegate_to_agent"
    description = (
        "Delegate a self-contained sub-task to another specialist agent. "
        "The target agent runs with its own role-specific system prompt "
        "and tool subset, then returns its final answer. Use this to split "
        "complex work into parallel or sequential sub-tasks. "
        "Recursion is strictly bounded: CFO -> CDO -> worker. Workers "
        "cannot delegate. Available targets depend on your current role."
    )
    parameters = {
        "agent": {
            "type": "string",
            "description": "Target agent role: cdo, actuary, quant, fpa, tax, or general.",
            "required": True,
        },
        "task": {
            "type": "string",
            "description": "Clear, self-contained description of the sub-task.",
            "required": True,
        },
        "context": {
            "type": "string",
            "description": "Optional context the target needs (data, format, constraints).",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        from .. import roles as _roles

        agent_raw = (args.get("agent") or "").strip().lower()
        task = (args.get("task") or "").strip()
        context = (args.get("context") or "").strip()
        caller = get_current_role()
        targets = _roles.delegation_targets(caller)

        if not agent_raw:
            return {"error": "agent is required", "available": targets}
        if not task:
            return {"error": "task is required"}

        if not _roles.is_valid(agent_raw):
            return {"error": f"unknown agent '{agent_raw}'", "available": targets}

        agent_canon = _roles.canonical(agent_raw)

        # ── Permission check ──────────────────────────────
        if not _roles.can_delegate(caller, agent_canon):
            return {
                "error": f"role '{caller}' cannot delegate to '{agent_canon}'",
                "available": targets,
            }

        # ── Depth check ───────────────────────────────────
        depth = get_depth()
        if depth >= _MAX_DEPTH:
            return {
                "error": f"max delegation depth {_MAX_DEPTH} reached",
                "path": get_path(),
            }

        # ── Cycle detection ───────────────────────────────
        path = get_path()
        if agent_canon in path:
            return {
                "error": f"cycle detected: '{agent_canon}' already in path",
                "path": path + [agent_canon],
            }

        sub_prompt = task
        if context:
            sub_prompt = task + "\n\n--- Context from " + caller + " ---\n" + context

        depth_token = _DELEGATION_DEPTH.set(depth + 1)
        path_token = _DELEGATION_PATH.set(tuple(path + [agent_canon]))
        try:
            from .. import orchestrator
            result = await orchestrator.run_agent(
                sub_prompt,
                session_uuid=None,
                role=agent_canon,
                on_event=None,
            )
        except Exception as e:
            return {
                "error": f"sub-agent '{agent_canon}' failed: "
                         f"{type(e).__name__}: {e}",
                "path": path + [agent_canon],
            }
        finally:
            _DELEGATION_DEPTH.reset(depth_token)
            _DELEGATION_PATH.reset(path_token)

        if not isinstance(result, dict):
            return {"error": "sub-agent returned unexpected type",
                    "raw": str(result)[:500]}

        if not result.get("ok"):
            return {
                "error": result.get("error") or "sub-agent failed",
                "agent": agent_canon,
                "path": path + [agent_canon],
            }

        return {
            "agent": agent_canon,
            "answer": result.get("answer", ""),
            "steps_count": len(result.get("steps", [])),
            "iterations": result.get("iterations", 1),
            "provider": result.get("provider"),
            "depth": depth + 1,
            "path": path + [agent_canon],
        }
