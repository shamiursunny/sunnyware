#!/usr/bin/env python3
"""Part 41 smoke test — wraps system_monitor.py and asserts a passing grade.

Schema (reports/system_health.json):
  score.score           -> float
  score.grade           -> str
  score.by_severity     -> {critical|high|medium|low: {earned, possible}}
  results               -> [{category, name, status, message, severity, detail}]
"""
import json
import pathlib
import subprocess
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
MONITOR = ROOT / "scripts" / "system_monitor.py"
REPORT_JSON = ROOT / "reports" / "system_health.json"
REPORT_MD = ROOT / "reports" / "system_health.md"
BASELINE = ROOT / "scripts" / "system_baseline.json"

PASS, FAIL = 0, 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def main():
    print("=" * 62)
    print(" Part 41 — System Monitor smoke test")
    print("=" * 62)

    check("system_monitor.py present", MONITOR.exists())
    if not MONITOR.exists():
        return 1

    print("\n  Running monitor (live HF, ~5–15s)...")
    result = subprocess.run(
        [sys.executable, str(MONITOR)],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    # rc=0 clean, rc=2 drift detected — both acceptable
    check(
        f"Monitor ran (rc={result.returncode})",
        result.returncode in (0, 2),
        detail=(result.stderr or "")[-200:] if result.returncode not in (0, 2) else "",
    )

    check("reports/system_health.json written", REPORT_JSON.exists())
    check("reports/system_health.md written", REPORT_MD.exists())

    if not REPORT_JSON.exists():
        print(f"\n  RESULT: {PASS} passed, {FAIL} failed")
        return 1

    try:
        data = json.load(REPORT_JSON.open(encoding="utf-8"))
    except Exception as e:
        check("report JSON parses", False, detail=str(e))
        print(f"\n  RESULT: {PASS} passed, {FAIL} failed")
        return 1
    check("report JSON parses", True)

    # ── Score ─────────────────────────────────────────────────
    score_obj = data.get("score", {})
    score = score_obj.get("score") if isinstance(score_obj, dict) else None
    grade = score_obj.get("grade", "") if isinstance(score_obj, dict) else ""
    check(f"Score >= 95 (got {score})", isinstance(score, (int, float)) and score >= 95)
    check(f"Grade present (got {grade!r})", bool(grade))

    # ── Results counts ────────────────────────────────────────
    results = data.get("results", [])
    check(f"Results non-empty ({len(results)} checks)", len(results) > 0)

    statuses = Counter(r.get("status", "?") for r in results)
    passes = statuses.get("PASS", 0)
    fails = statuses.get("FAIL", 0)
    warns = statuses.get("WARN", 0)

    check(f"Zero FAIL checks (got {fails})", fails == 0)
    check(f"WARN <= 2 (got {warns})", warns <= 2)
    print(f"        {passes} PASS / {fails} FAIL / {warns} WARN")

    # ── Critical severity must be 100% ───────────────────────
    crit = [r for r in results if r.get("severity") == "critical"]
    crit_fail = [r for r in crit if r.get("status") != "PASS"]
    check(
        f"All critical checks pass ({len(crit) - len(crit_fail)}/{len(crit)})",
        len(crit) > 0 and len(crit_fail) == 0,
    )
    for r in crit_fail[:3]:
        print(f"        ✗ {r.get('category')}/{r.get('name')}")

    # ── by_severity sanity ───────────────────────────────────
    by_sev = score_obj.get("by_severity", {}) if isinstance(score_obj, dict) else {}
    if by_sev:
        check("by_severity.critical 100%",
              by_sev.get("critical", {}).get("earned", 0)
              == by_sev.get("critical", {}).get("possible", -1))
        check("by_severity.high 100%",
              by_sev.get("high", {}).get("earned", 0)
              == by_sev.get("high", {}).get("possible", -1))

    # ── Baseline ─────────────────────────────────────────────
    check("Baseline file present", BASELINE.exists())
    if BASELINE.exists():
        try:
            json.load(BASELINE.open(encoding="utf-8"))
            check("Baseline JSON parses", True)
        except Exception as e:
            check("Baseline JSON parses", False, detail=str(e))

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
