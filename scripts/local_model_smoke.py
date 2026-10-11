#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Local model smoke test - hits the HF Space smoke endpoint.

WARNING: This freezes the entire HF Space for ~5-10 minutes.
Do not run while others are using the Space.
"""

import sys
import time

import httpx


BASE = "https://shamiur-sunnyware.hf.space"


def main():
    print("=" * 60)
    print(" Local Model Smoke Test")
    print("=" * 60)
    print()
    print("This freezes the HF Space for ~5-10 minutes.")
    print("The WebUI will not respond during this test.")
    print()
    print("Starting test...")
    print()

    t0 = time.time()
    try:
        r = httpx.post(
            BASE + "/api/local-model/smoke",
            timeout=900.0,
        )
    except Exception as e:
        print("[FAIL] Request error: " + type(e).__name__ + ": " + str(e))
        return 1

    elapsed = int(time.time() - t0)
    print("Response received in " + str(elapsed) + " sec")
    print()

    if r.status_code != 200:
        print("[FAIL] HTTP " + str(r.status_code))
        print(r.text[:500])
        return 1

    try:
        data = r.json()
    except Exception as e:
        print("[FAIL] Cannot parse JSON: " + str(e))
        print(r.text[:500])
        return 1

    print("Total tests:  " + str(data.get("total_tests")))
    print("Passed:       " + str(data.get("passed")))
    print("Failed:       " + str(data.get("failed")))
    print("Total time:   " + str(data.get("total_latency_ms")) + " ms")
    print()
    print("-" * 60)
    print("Per-test results")
    print("-" * 60)
    print()

    for entry in data.get("results", []):
        name = entry.get("test", "?")
        ok = entry.get("ok")
        mark = "PASS" if ok else "FAIL"
        print("[" + mark + "] " + name)
        for k, v in entry.items():
            if k in ("test", "ok"):
                continue
            print("         " + k + ": " + str(v)[:120])
        print()

    print("=" * 60)
    if data.get("failed", 0) == 0:
        print(" ALL LOCAL MODEL TESTS PASSED")
        return 0
    else:
        print(" " + str(data.get("failed")) + " of " + str(data.get("total_tests")) + " tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
