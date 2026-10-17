# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 160: per-tool circuit breaker.

If a tool fails N consecutive times, its breaker opens and further
calls return a synthetic 'circuit_open' error for M seconds. This
stops a broken upstream (e.g. a flaky external API) from burning
through the agent's iteration budget.

Config (all opt-in; defaults keep behavior unchanged):
  SUNNYWARE_TOOL_BREAKER_FAILS=5         consecutive failures to trip
  SUNNYWARE_TOOL_BREAKER_COOLDOWN_S=60   seconds to stay open
  SUNNYWARE_TOOL_BREAKER_ENABLED=1       master switch (default on)

State lives in-process. Reset via reset() or the /api/tools/circuits
endpoints.
"""

import os
import time
from typing import Optional


_STATE = {}
# { tool_name: {"consecutive_fails": int, "total_fails": int,
#               "total_success": int, "opened_at": float,
#               "last_error": str, "last_call_at": float} }


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or str(default))
    except Exception:
        return default


def enabled() -> bool:
    v = (os.getenv("SUNNYWARE_TOOL_BREAKER_ENABLED", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def fails_threshold() -> int:
    return max(1, _env_int("SUNNYWARE_TOOL_BREAKER_FAILS", 5))


def rpm_limit() -> int:
    """Part 173: per-tool RPM speed breaker. 0 = disabled."""
    return max(0, _env_int("SUNNYWARE_TOOL_RATE_LIMIT_PER_MINUTE", 0))


def cooldown_seconds() -> int:
    return max(1, _env_int("SUNNYWARE_TOOL_BREAKER_COOLDOWN_S", 60))


def _get(tool_name: str) -> dict:
    s = _STATE.get(tool_name)
    if s is None:
        s = {
            "consecutive_fails": 0,
            "total_fails": 0,
            "total_success": 0,
            "opened_at": 0.0,
            "last_error": "",
            "last_call_at": 0.0,
            "recent_calls": [],
            "rate_cooldown_until": 0.0,
        }
        _STATE[tool_name] = s
    return s


def is_open(tool_name: str) -> bool:
    """True if breaker is currently open (call should be short-circuited)."""
    if not enabled() or not tool_name:
        return False
    s = _STATE.get(tool_name)
    if not s or not s.get("opened_at"):
        return False
    remaining = s["opened_at"] + cooldown_seconds() - time.time()
    return remaining > 0


def remaining_open_seconds(tool_name: str) -> float:
    s = _STATE.get(tool_name)
    if not s or not s.get("opened_at"):
        return 0.0
    return max(0.0, s["opened_at"] + cooldown_seconds() - time.time())


def check(tool_name: str) -> dict:
    """Return {allow: bool, reason?, retry_after?}."""
    if not enabled() or not tool_name:
        return {"allow": True}
    
    # 1. Check failure breaker first (highest priority)
    if is_open(tool_name):
        return {
            "allow": False,
            "reason": "circuit_open",
            "retry_after": int(remaining_open_seconds(tool_name)) + 1,
        }
        
    # 2. Check rate limit (speedbreaker)
    limit = rpm_limit()
    if limit > 0:
        s = _get(tool_name)
        now = time.time()
        # If already in rate cooldown
        if s.get("rate_cooldown_until", 0.0) > now:
            return {
                "allow": False,
                "reason": "rate_limited",
                "retry_after": int(s["rate_cooldown_until"] - now) + 1,
            }
        # Filter calls older than 60s
        s["recent_calls"] = [t for t in s.get("recent_calls", []) if now - t < 60]
        if len(s["recent_calls"]) >= limit:
            s["rate_cooldown_until"] = now + 60
            return {
                "allow": False,
                "reason": "rate_limited",
                "retry_after": 60,
            }
            
    return {"allow": True}


def record(tool_name: str, ok: bool, error: str = "") -> None:
    """Update state after a tool call completes."""
    if not enabled() or not tool_name:
        return
    s = _get(tool_name)
    s["last_call_at"] = time.time()
    
    # Part 173: track recent calls for RPM
    if rpm_limit() > 0:
        s.setdefault("recent_calls", []).append(s["last_call_at"])
        
    if ok:
        s["total_success"] += 1
        # Reset consecutive counter and close the breaker on success
        s["consecutive_fails"] = 0
        s["opened_at"] = 0.0
        s["last_error"] = ""
        return
    s["total_fails"] += 1
    s["consecutive_fails"] += 1
    s["last_error"] = (error or "")[:200]
    if s["consecutive_fails"] >= fails_threshold():
        # Trip the breaker
        s["opened_at"] = time.time()
        # Part 171: emit circuit.open event (flows to outbound webhooks
        # via audit.log)
        try:
            from . import audit as _audit
            _audit.log(
                "circuit.open", actor="breaker", ok=False,
                detail="tool '" + str(tool_name) + "' tripped after "
                       + str(fails_threshold()) + " fails",
                tool=tool_name,
                last_error=str(s.get("last_error", ""))[:200],
            )
        except Exception:
            pass


def snapshot() -> dict:
    now = time.time()
    out = {
        "enabled": enabled(),
        "fails_threshold": fails_threshold(),
        "cooldown_seconds": cooldown_seconds(),
        "tools": [],
    }
    for name, s in sorted(_STATE.items()):
        opened = float(s.get("opened_at") or 0.0)
        remaining = (opened + cooldown_seconds() - now) if opened else 0.0
        # Filter recent_calls to only last 60s for accurate count
        recent = [t for t in s.get("recent_calls", []) if now - t < 60]
        rate_cool = max(0.0, s.get("rate_cooldown_until", 0.0) - now)
        out["tools"].append({
            "name": name,
            "open": bool(opened and remaining > 0),
            "remaining_open_s": int(max(0.0, remaining)),
            "consecutive_fails": int(s.get("consecutive_fails", 0)),
            "total_fails": int(s.get("total_fails", 0)),
            "total_success": int(s.get("total_success", 0)),
            "last_error": s.get("last_error", ""),
            "last_call_at": s.get("last_call_at", 0.0),
            "rpm_limit": int(rpm_limit()),
            "rpm_current": len(recent),
            "rate_cooldown_s": int(rate_cool),
        })
    return out


def reset(tool_name: Optional[str] = None) -> int:
    """Clear breaker state for one tool or all. Returns count cleared."""
    if tool_name:
        existed = tool_name in _STATE
        _STATE.pop(tool_name, None)
        return 1 if existed else 0
    n = len(_STATE)
    _STATE.clear()
    return n
