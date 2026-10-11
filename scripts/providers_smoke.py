#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Client script for /api/providers/smoke."""

import sys
import httpx

BASE = "https://shamiur-sunnyware.hf.space"


def main():
    print("=" * 70)
    print(" Provider Smoke Test")
    print("=" * 70)
    print()

    try:
        r = httpx.post(BASE + "/api/providers/smoke", timeout=180.0)
    except Exception as e:
        print("[FAIL] " + type(e).__name__ + ": " + str(e))
        return 1

    print("HTTP " + str(r.status_code))
    if r.status_code != 200:
        print(r.text[:500])
        return 1

    d = r.json()
    print("Total:  " + str(d.get("total")))
    print("Passed: " + str(d.get("passed")))
    print("Failed: " + str(d.get("failed")))
    print()
    print("-" * 70)

    for entry in d.get("results", []):
        name = entry.get("provider", "?")
        ok = entry.get("ok")
        if entry.get("skipped"):
            print("[SKIP] " + name + " - " + entry["skipped"])
            continue
        mark = "PASS" if ok else "FAIL"
        print("[" + mark + "] " + name)
        print("       configured:  " + str(entry.get("configured_model")))
        print("       resolved:    " + str(entry.get("resolved_model")) +
              "  (source=" + str(entry.get("resolution_source")) + ")")
        print("       available:   " + str(entry.get("available_count")) + " models")
        print("       latency_ms:  " + str(entry.get("latency_ms")))
        print("       sample:      " + str(entry.get("sample"))[:80])
        if entry.get("error"):
            print("       error:       " + str(entry.get("error"))[:200])
        print()

    print("=" * 70)
    if d.get("failed", 0) == 0:
        print(" ALL PROVIDERS OK")
        return 0
    print(" " + str(d.get("failed")) + " provider(s) failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
