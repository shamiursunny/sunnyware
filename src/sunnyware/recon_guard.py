# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 162: recon-path guard.

Blocks common scanner probes (/.env, /.git/config, /wp-admin, *.php,
*.sql, etc.) with HTTP 403. Tracks hit counters per pattern.

Design: pure check() with optional record() side effect. Never throws
into the request path. Never touches the app's own prefixes
(/api/, /health, /static/, /docs, /redoc, /openapi.json, /.well-known/,
/favicon).

Config (all optional; default on):
  SUNNYWARE_RECON_GUARD_ENABLED=1      master switch
  SUNNYWARE_RECON_LOG_TO_AUDIT=1       also log hits to audit trail
  SUNNYWARE_RECON_RECENT_MAX=50        cap on the in-memory recent list
"""

import os
import re
import time
from typing import Optional, Tuple


# ─── patterns ───

# Prefixes we always allow, even if they'd otherwise match a pattern.
ALLOW_PREFIXES = (
    "/api/",
    "/health",
    "/static/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon",
    "/.well-known/",
    "/tools",
)

# High-signal probe patterns. Anchored where it matters to avoid
# false positives on legitimate paths (e.g. /api/foo.php would still
# be blocked, but that's fine — no such route exists).
BLOCK_PATTERNS = (
    r"/\.env(\.|$|/|$)",
    r"/\.git($|/)",
    r"/\.svn($|/)",
    r"/\.hg($|/)",
    r"/\.aws/",
    r"/\.ssh/",
    r"/\.DS_Store$",
    r"/wp-admin($|/)",
    r"/wp-login",
    r"/wp-content($|/)",
    r"/wp-includes($|/)",
    r"/xmlrpc\.php$",
    r"/phpmyadmin",
    r"/pma($|/)",
    r"/adminer",
    r"/cgi-bin/",
    r"/vendor/phpunit",
    r"/vendor/composer",
    r"/actuator($|/)",
    r"/admin\.php$",
    r"/setup\.php$",
    r"/install\.php$",
    r"/shell\.php$",
    r"/c99\.php$",
    r"/r57\.php$",
    r"/backup\.sql($|\.|$)",
    r"/db\.sql($|\.|$)",
    r"/dump\.sql($|\.|$)",
    r"/config\.json$",
    r"/secrets\.json$",
    # catch-alls for server-side script probes
    r"\.php$",
    r"\.asp$",
    r"\.aspx$",
    r"\.jsp$",
)


# ─── state ───

_STATS = {
    "blocked_total": 0,
    "by_pattern": {},
    "by_ip": {},
    "first_ts": None,
    "last_ts": None,
    "last_path": "",
    "last_ip": "",
    "recent": [],
}


def enabled() -> bool:
    v = (os.getenv("SUNNYWARE_RECON_GUARD_ENABLED", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def _log_to_audit() -> bool:
    v = (os.getenv("SUNNYWARE_RECON_LOG_TO_AUDIT", "1") or "1").lower()
    return v not in ("0", "false", "no", "off")


def _recent_max() -> int:
    try:
        return max(1, min(int(os.getenv("SUNNYWARE_RECON_RECENT_MAX", "50")),
                          1000))
    except Exception:
        return 50


def _is_allowed(path: str) -> bool:
    for p in ALLOW_PREFIXES:
        if path.startswith(p):
            return True
    return False


def check(path: str) -> dict:
    """Return {block: bool, pattern?: str}. Pure; no side effects."""
    if not enabled() or not path:
        return {"block": False}
    if _is_allowed(path):
        return {"block": False}
    for pat in BLOCK_PATTERNS:
        try:
            if re.search(pat, path, re.IGNORECASE):
                return {"block": True, "pattern": pat}
        except Exception:
            continue
    return {"block": False}


def record(path: str, ip: str = "", pattern: str = "") -> None:
    """Increment counters for a blocked hit. Safe on any input."""
    if not enabled():
        return
    try:
        now = time.time()
        _STATS["blocked_total"] += 1
        _STATS["by_pattern"][pattern] = _STATS["by_pattern"].get(pattern, 0) + 1
        if ip:
            _STATS["by_ip"][ip] = _STATS["by_ip"].get(ip, 0) + 1
        _STATS["last_ts"] = now
        _STATS["last_path"] = str(path)[:300]
        _STATS["last_ip"] = str(ip)[:60]
        if _STATS["first_ts"] is None:
            _STATS["first_ts"] = now
        _STATS["recent"].append({
            "ts": now, "path": str(path)[:300],
            "ip": str(ip)[:60], "pattern": pattern,
        })
        cap = _recent_max()
        if len(_STATS["recent"]) > cap:
            _STATS["recent"] = _STATS["recent"][-cap:]
    except Exception:
        pass
    # Optional audit-log integration (best-effort)
    if _log_to_audit():
        try:
            from . import audit as _audit
            _audit.log("recon.block", actor=ip or "unknown", ok=False,
                       detail=f"path={path[:120]} pattern={pattern}",
                       path=path[:200], pattern=pattern)
        except Exception:
            pass


def stats() -> dict:
    snap = {
        "enabled": enabled(),
        "log_to_audit": _log_to_audit(),
        "patterns_count": len(BLOCK_PATTERNS),
        "blocked_total": _STATS["blocked_total"],
        "by_pattern": dict(_STATS["by_pattern"]),
        "by_ip_top": sorted(_STATS["by_ip"].items(),
                            key=lambda kv: -kv[1])[:10],
        "first_ts": _STATS["first_ts"],
        "last_ts": _STATS["last_ts"],
        "last_path": _STATS["last_path"],
        "last_ip": _STATS["last_ip"],
        "recent": list(_STATS["recent"])[-_recent_max():],
    }
    return snap


def reset() -> int:
    """Clear all counters. Returns previous blocked_total."""
    prev = _STATS["blocked_total"]
    _STATS["blocked_total"] = 0
    _STATS["by_pattern"] = {}
    _STATS["by_ip"] = {}
    _STATS["first_ts"] = None
    _STATS["last_ts"] = None
    _STATS["last_path"] = ""
    _STATS["last_ip"] = ""
    _STATS["recent"] = []
    return prev
