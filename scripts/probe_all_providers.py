#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Probe all configured LLM providers and list their available models.

Reads keys from local .env or env vars. Hits each provider's /models
endpoint and prints what's actually available on your account.
"""

import os
import sys
from pathlib import Path

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv(Path(".env"))
except Exception:
    pass


PROVIDERS = [
    {
        "name": "mistral",
        "url": "https://api.mistral.ai/v1/models",
        "key_env": "MISTRAL_API_KEY",
        "alt_key_env": "MISTRAL_KEY",
    },
    {
        "name": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/models",
        "key_env": "GEMINI_API_KEY",
    },
    {
        "name": "openrouter",
        "url": "https://openrouter.ai/api/v1/models",
        "key_env": "OPENROUTER_API_KEY",
        "public": True,  # /models endpoint is public for openrouter
    },
    {
        "name": "groq",
        "url": "https://api.groq.com/openai/v1/models",
        "key_env": "GROQ_API_KEY",
    },
    {
        "name": "nvidia",
        "url": "https://integrate.api.nvidia.com/v1/models",
        "key_env": "NVIDIA_API_KEY",
    },
]


def get_key(provider):
    for env in [provider.get("key_env"), provider.get("alt_key_env")]:
        if env:
            k = os.getenv(env, "").strip()
            if k:
                return k
    return ""


def probe(provider):
    name = provider["name"]
    key = get_key(provider)
    print("=" * 70)
    print(f" {name.upper()}")
    print("=" * 70)
    if not key and not provider.get("public"):
        print(f"  [SKIP] no key in env ({provider.get('key_env')})")
        print()
        return
    if key:
        print(f"  key: {key[:8]}...{key[-4:] if len(key) > 12 else ''}")
    else:
        print(f"  key: (none - public endpoint)")
    try:
        r = httpx.get(
            provider["url"],
            headers={"Authorization": f"Bearer {key}"} if key else {},
            timeout=15.0,
        )
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")
        print()
        return
    print(f"  HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"  body: {r.text[:300]}")
        print()
        return
    try:
        data = r.json()
    except Exception as e:
        print(f"  [ERROR] parse: {e}")
        print()
        return

    # OpenAI-style response
    models = data.get("data") or data.get("models") or []
    ids = []
    for m in models:
        if isinstance(m, dict):
            mid = m.get("id") or m.get("name") or "?"
            ids.append(mid)
        else:
            ids.append(str(m))
    ids.sort()

    print(f"  total models: {len(ids)}")
    print()

    # Filter for free/interesting ones
    if name == "openrouter":
        free = [i for i in ids if ":free" in i]
        print(f"  FREE models on OpenRouter ({len(free)}):")
        for i in free:
            print(f"    {i}")
    else:
        print(f"  All models:")
        for i in ids:
            print(f"    {i}")
    print()


def main():
    print()
    print("#" * 70)
    print("# Provider Model Probe")
    print("#" * 70)
    print()
    for p in PROVIDERS:
        probe(p)
    print("#" * 70)
    print("# Done")
    print("#" * 70)


if __name__ == "__main__":
    main()
