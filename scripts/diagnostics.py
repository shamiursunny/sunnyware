#!/usr/bin/env python3
"""CLI: run Sunnyware diagnostics startup checks."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from sunnyware.diagnostics import run_startup_checks, get_report

def _strip_volatile(record: dict) -> dict:
    """Remove fields that change every run (id, timestamp, session_id)."""
    return {k: v for k, v in record.items()
            if k not in ("id", "timestamp", "session_id")}


def _stable_report(report: dict) -> dict:
    """Produce a deterministic report for hashing/attestation."""
    stable = {"summary": dict(sorted(report.get("summary", {}).items())), "records": {}}
    for sev, items in sorted(report.get("records", {}).items()):
        stripped = [_strip_volatile(r) for r in items]
        stripped.sort(key=lambda r: (r.get("cls", ""), r.get("message", "")))
        stable["records"][sev] = stripped
    return stable


def main():
    attest = "--attest" in sys.argv
    print("Running startup diagnostics...")
    summary = run_startup_checks()
    print("Startup summary:", {"status": summary.get("status"),
                                "records": summary.get("records")})
    report = get_report()

    if attest:
        # Deterministic output for CI/attestation hashing
        print(json.dumps(_stable_report(report), indent=2, sort_keys=True))
    else:
        print(json.dumps(report, indent=2))
        out = Path("data/diagnostics/report.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report written: {out}")

    for sev in ("error", "fatal"):
        if report["summary"].get(sev, 0) > 0:
            print(f"[FAIL] {sev} records present"); return 1
    print("[PASS] no errors or fatals"); return 0

if __name__ == "__main__":
    sys.exit(main())
