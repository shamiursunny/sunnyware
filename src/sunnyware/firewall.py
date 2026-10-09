# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""IP allowlist + security headers (opt-in via env)."""

import ipaddress
import os
from typing import Optional


_CACHE = None


def _parse_allowlist() -> list:
    """Parse SUNNYWARE_IP_ALLOWLIST. Returns list of ip_network objects."""
    raw = (os.getenv("SUNNYWARE_IP_ALLOWLIST") or "").strip()
    if not raw:
        return []
    out = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            # Accept single IP or CIDR
            net = ipaddress.ip_network(item, strict=False)
            out.append(net)
        except ValueError:
            continue
    return out


def load_allowlist(reload: bool = False) -> list:
    global _CACHE
    if _CACHE is None or reload:
        _CACHE = _parse_allowlist()
    return _CACHE


def enabled() -> bool:
    return len(load_allowlist()) > 0


def security_headers_enabled() -> bool:
    v = (os.getenv("SUNNYWARE_SECURITY_HEADERS", "true") or "").lower()
    return v not in ("false", "0", "no", "off")


def extract_client_ip(scope: dict) -> str:
    """Return client IP — checks X-Forwarded-For (proxies) then socket peer."""
    headers = scope.get("headers") or []
    xff = None
    for k, v in headers:
        if not isinstance(k, (bytes, bytearray)):
            continue
        if k.lower() == b"x-forwarded-for":
            try:
                # Take leftmost (origin) entry
                xff = v.decode("ascii", errors="replace").split(",")[0].strip()
            except Exception:
                pass
            break
    if xff:
        return xff
    client = scope.get("client")
    if client and isinstance(client, (list, tuple)) and len(client) >= 1:
        return str(client[0])
    return ""


def is_allowed(ip: str) -> bool:
    """Return True if ip is in allowlist (or if allowlist is disabled)."""
    nets = load_allowlist()
    if not nets:
        return True
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in nets:
        try:
            if addr in net:
                return True
        except Exception:
            continue
    return False


def build_security_headers(scheme: str = "https") -> list:
    """Return list of (name_bytes, value_bytes) security headers."""
    hdrs = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
        (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
    ]
    if scheme == "https":
        hdrs.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
    return hdrs


def status() -> dict:
    nets = load_allowlist(reload=True)
    return {
        "ip_allowlist_enabled": len(nets) > 0,
        "allowed_networks": [str(n) for n in nets],
        "security_headers_enabled": security_headers_enabled(),
        "headers_applied": [h.decode() for h, _ in build_security_headers("https")],
    }
