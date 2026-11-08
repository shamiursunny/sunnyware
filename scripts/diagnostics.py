#!/usr/bin/env python3
"""CLI: run Sunnyware diagnostics startup checks."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from sunnyware.diagnostics import run_startup_checks, get_report

def main():
    print("Running startup diagnostics...")
    summary = run_startup_checks()
    print("Startup summary:", summary)
    report = get_report()
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
