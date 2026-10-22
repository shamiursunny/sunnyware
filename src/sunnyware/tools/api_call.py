# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Generic REST API caller with SSRF protection (Part 56).

Blocks private/internal hosts. Optional SUNNYWARE_API_ALLOWLIST env var
(comma-separated domains) further restricts allowed targets. Response
body capped at 200 KB. Returns structured JSON when the server sends it.
"""
import ipaddress
import json
import os
import socket
from typing import Optional
from urllib.parse import urlparse

try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    _HAS_HTTPX = False


_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}
_MAX_RESPONSE_BYTES = 200 * 1024
_MAX_TIMEOUT = 30.0
_DEFAULT_TIMEOUT = 15.0
_KEEP_HEADERS = (
    "content-type", "content-length", "server", "date",
    "x-ratelimit-remaining", "x-ratelimit-limit", "retry-after", "location",
)


def _allowlist() -> set:
    raw = os.getenv("SUNNYWARE_API_ALLOWLIST") or ""
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _is_private_host(host: str) -> bool:
    """Block localhost, loopback, link-local, reserved, and RFC1918 ranges."""
    if not host:
        return True
    h = host.lower()
    if h in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    try:
        infos = socket.getaddrinfo(h, None)
    except Exception:
        return False  # let httpx surface the DNS error
    for _fam, _t, _p, _c, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def _check_url(url: str) -> Optional[str]:
    """Return None if URL is allowed, else an error message."""
    if not url:
        return "url is required"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "url scheme must be http or https"
    host = parsed.hostname or ""
    if not host:
        return "url has no host"
    if _is_private_host(host):
        return "blocked: private/internal host '{}'".format(host)
    allow = _allowlist()
    if allow:
        host_l = host.lower()
        if not any(host_l == p or host_l.endswith("." + p) for p in allow):
            return "blocked: host '{}' not in SUNNYWARE_API_ALLOWLIST".format(host)
    return None


class ApiCallTool:
    name = "api_call"
    description = "Make an HTTP GET/POST/PUT/DELETE request to any URL. Triggers: API call, HTTP request, GET request, POST to URL, fetch API. Input: url and method. Returns response body and status."
    parameters = {
        "url": {
            "type": "string",
            "description": "Full http(s) URL",
            "required": True,
        },
        "method": {
            "type": "string",
            "description": "GET/POST/PUT/PATCH/DELETE/HEAD (default GET)",
            "required": False,
        },
        "headers": {
            "type": "object",
            "description": "Optional request headers object",
            "required": False,
        },
        "json_body": {
            "type": "object",
            "description": "Optional JSON body (auto-sets Content-Type: application/json)",
            "required": False,
        },
        "timeout": {
            "type": "number",
            "description": "Seconds (default 15, max 30)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_HTTPX:
            return {"error": "httpx not installed"}
        url = (args.get("url") or "").strip()
        err = _check_url(url)
        if err:
            return {"error": err}
        method = (args.get("method") or "GET").upper()
        if method not in _ALLOWED_METHODS:
            return {"error": "method must be one of " + str(sorted(_ALLOWED_METHODS))}
        try:
            timeout = float(args.get("timeout") or _DEFAULT_TIMEOUT)
        except (TypeError, ValueError):
            return {"error": "timeout must be a number"}
        timeout = max(1.0, min(timeout, _MAX_TIMEOUT))

        headers = args.get("headers") or {}
        if not isinstance(headers, dict):
            return {"error": "headers must be an object"}
        headers = {str(k): str(v) for k, v in headers.items()}

        body = args.get("json_body")
        json_kw = None
        if body is not None:
            if not isinstance(body, (dict, list)):
                return {"error": "json_body must be an object or array"}
            json_kw = body
            headers.setdefault("Content-Type", "application/json")
        headers.setdefault("User-Agent", "sunnyware-agent/1.0")

        try:
            async with httpx.AsyncClient(timeout=timeout,
                                         follow_redirects=True) as client:
                r = await client.request(method, url,
                                         headers=headers, json=json_kw)
        except httpx.TimeoutException:
            return {"error": "timeout after {}s".format(timeout)}
        except Exception as e:
            return {"error": "{}: {}".format(type(e).__name__, e)}

        raw = r.content
        truncated = False
        if len(raw) > _MAX_RESPONSE_BYTES:
            raw = raw[:_MAX_RESPONSE_BYTES]
            truncated = True

        parsed_json = None
        text = None
        ct = (r.headers.get("content-type") or "").lower()
        try:
            if "json" in ct or raw.lstrip().startswith(b"{"):
                parsed_json = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            parsed_json = None
        if parsed_json is None:
            text = raw.decode("utf-8", errors="replace")

        out = {
            "status_code": r.status_code,
            "method": method,
            "url": str(r.url),
            "content_type": ct,
            "bytes": len(r.content),
            "truncated": truncated,
        }
        if parsed_json is not None:
            out["json"] = parsed_json
        else:
            out["text"] = text
        out["headers"] = {
            k: v for k, v in r.headers.items()
            if k.lower() in _KEEP_HEADERS
        }
        return out
