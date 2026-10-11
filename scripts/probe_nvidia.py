#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Probe NVIDIA NIM to verify API key + discover tool-calling models.

Usage:
    export NVIDIA_API_KEY=nvapi-...
    python scripts/probe_nvidia.py
"""

import os
import sys

import httpx


BASE = "https://integrate.api.nvidia.com/v1"


def main():
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not key:
        print("ERROR: NVIDIA_API_KEY not set")
        print("Run: export NVIDIA_API_KEY=nvapi-...")
        return 1

    print("=" * 60)
    print(" NVIDIA NIM Probe")
    print("=" * 60)
    print()

    print("[1] Fetching model list...")
    try:
        r = httpx.get(
            BASE + "/models",
            headers={"Authorization": "Bearer " + key},
            timeout=15.0,
        )
    except Exception as e:
        print("    FAIL: " + type(e).__name__ + ": " + str(e))
        return 1

    print("    HTTP " + str(r.status_code))
    if r.status_code != 200:
        print("    Body: " + r.text[:400])
        return 1

    try:
        data = r.json()
        models = [m.get("id") for m in data.get("data", [])]
    except Exception as e:
        print("    FAIL to parse: " + str(e))
        return 1

    print("    Total models: " + str(len(models)))
    print()

    print("[2] Tool-calling candidates:")
    known = [
        "meta/llama-4-maverick-17b-128e-instruct",
        "meta/llama-4-scout-17b-16e-instruct",
        "mistralai/mistral-small-3.2-24b-instruct-2506",
        "nvidia/llama-3.1-nemotron-70b-instruct",
        "meta/llama-3.3-70b-instruct",
        "meta/llama-3.1-70b-instruct",
    ]
    found = []
    for k in known:
        if k in models:
            found.append(k)
            print("    [OK]      " + k)
        else:
            print("    [MISSING] " + k)
    print()

    if found:
        print("[3] Recommended first: " + found[0])
    else:
        print("[3] No known tool-calling model present in your account.")
        print("    Check https://build.nvidia.com/models")
    print()

    if found:
        print("[4] Test completion with " + found[0] + "...")
        try:
            r = httpx.post(
                BASE + "/chat/completions",
                headers={
                    "Authorization": "Bearer " + key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": found[0],
                    "messages": [{"role": "user", "content": "Say hi in one word."}],
                    "max_tokens": 30,
                },
                timeout=30.0,
            )
            print("    HTTP " + str(r.status_code))
            if r.status_code == 200:
                d = r.json()
                content = d["choices"][0]["message"].get("content", "")
                print("    Response: " + content[:100])
            else:
                print("    Body: " + r.text[:400])
        except Exception as e:
            print("    FAIL: " + type(e).__name__ + ": " + str(e))

    print()
    print("=" * 60)
    print(" Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
