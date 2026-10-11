# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Auto model resolver (Part 33).

Probes each provider /models endpoint and picks the best available model
when the configured one is retired or unavailable. Caches per provider
with TTL, so we only probe once per hour.

Env vars:
  MODEL_AUTORESOLVE=1  (default ON). Set 0 to disable and always use
                       the configured model verbatim.
"""

import os
import time
from typing import Optional

import httpx


SUCCESS_TTL = 3600.0   # 1 hour
FAILURE_TTL = 300.0    # 5 min (retry sooner on transient failures)


# Per-provider preference list (ordered: best -> fallback)
PREFERENCES = {
    "mistral": [
        "mistral-medium-latest",
        "mistral-medium-3.5",
        "mistral-medium-3",
        "mistral-medium",
        "ministral-14b-latest",
        "ministral-8b-latest",
        "mistral-small-latest",
        "ministral-3b-latest",
    ],
    "gemini": [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ],
    "openrouter": [
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "thinkingmachines/inkling:free",
        "cohere/north-mini-code:free",
        "liquid/lfm-2.5-2.6b:free",
    ],
    "groq": [
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "meta-llama/llama-3.3-70b-versatile",
    ],
    "nvidia": [
        "meta/llama-4-maverick-17b-128e-instruct",
        "meta/llama-4-scout-17b-16e-instruct",
        "mistralai/mistral-small-3.2-24b-instruct-2506",
        "meta/llama-3.3-70b-instruct",
        "nvidia/llama-3.1-nemotron-70b-instruct",
    ],
}


_CACHE = {}


def _enabled() -> bool:
    v = (os.getenv("MODEL_AUTORESOLVE", "1") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _strip_prefix(mid):
    if isinstance(mid, str) and mid.startswith("models/"):
        return mid[7:]
    return mid


async def _fetch_models(base_url, api_key):
    """GET {base_url}/models. Returns list of ids or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            r = await client.get(
                base_url.rstrip("/") + "/models",
                headers={"Authorization": "Bearer " + (api_key or "")},
            )
            if r.status_code != 200:
                return None
            data = r.json()
    except Exception:
        return None
    items = data.get("data") or data.get("models") or []
    out = []
    for m in items:
        if isinstance(m, dict):
            mid = m.get("id") or m.get("name")
            if mid:
                out.append(_strip_prefix(str(mid)))
        else:
            out.append(_strip_prefix(str(m)))
    return out


def _pick_best(available, preferences):
    if not available:
        return None
    avail_set = set(available)
    for pref in preferences:
        if pref in avail_set:
            return pref
    return None


async def resolve(provider_name, base_url, api_key, configured_model):
    """Returns dict with model, source, available, error."""
    name = (provider_name or "default").lower()

    if not _enabled():
        return {"model": configured_model, "source": "disabled",
                "available": 0, "error": ""}

    cached = _CACHE.get(name)
    now = time.time()
    if cached:
        ttl = SUCCESS_TTL if cached.get("source") in ("configured", "auto") else FAILURE_TTL
        if (now - cached.get("fetched_at", 0)) < ttl:
            return {
                "model": cached.get("resolved") or configured_model,
                "source": cached.get("source", "cache"),
                "available": len(cached.get("models") or []),
                "error": cached.get("error", ""),
            }

    available = await _fetch_models(base_url, api_key)
    if available is None:
        _CACHE[name] = {"models": [], "resolved": configured_model,
                        "source": "fallback", "fetched_at": now,
                        "error": "models_endpoint_unreachable"}
        return {"model": configured_model, "source": "fallback",
                "available": 0, "error": "models_endpoint_unreachable"}

    cfg_norm = _strip_prefix(configured_model)
    if cfg_norm and cfg_norm in available:
        _CACHE[name] = {"models": available, "resolved": cfg_norm,
                        "source": "configured", "fetched_at": now, "error": ""}
        return {"model": cfg_norm, "source": "configured",
                "available": len(available), "error": ""}

    best = _pick_best(available, PREFERENCES.get(name, []))
    if best:
        _CACHE[name] = {"models": available, "resolved": best,
                        "source": "auto", "fetched_at": now, "error": ""}
        return {"model": best, "source": "auto",
                "available": len(available), "error": ""}

    _CACHE[name] = {"models": available, "resolved": configured_model,
                    "source": "fallback", "fetched_at": now,
                    "error": "no_preference_match"}
    return {"model": configured_model, "source": "fallback",
            "available": len(available), "error": "no_preference_match"}


def snapshot():
    """Current cache state — for /api/models/resolve."""
    out = {}
    for name, entry in _CACHE.items():
        out[name] = {
            "resolved": entry.get("resolved"),
            "source": entry.get("source"),
            "available_count": len(entry.get("models") or []),
            "age_sec": int(time.time() - entry.get("fetched_at", 0)),
            "error": entry.get("error", ""),
        }
    return out


def invalidate(provider_name=None):
    if provider_name:
        _CACHE.pop(provider_name.lower(), None)
    else:
        _CACHE.clear()
