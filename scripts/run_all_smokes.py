# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Run every scripts/smoke_test_part*.py with a per-file timeout.

Exit 0 if all pass. Exit 1 if any fail. Prints a compact summary at
the end so CI logs stay readable.

Usage:
    python scripts/run_all_smokes.py
    python scripts/run_all_smokes.py --timeout 60
    python scripts/run_all_smokes.py --fail-fast
    python scripts/run_all_smokes.py --list
    python scripts/run_all_smokes.py --only 160 161 162
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ENV = dict(os.environ)
ENV.setdefault("PYTHONIOENCODING", "utf-8")
ENV.setdefault("PYTHONUTF8", "1")


def find_smokes():
    return sorted(SCRIPTS.glob("smoke_test_part*.py"))


# Dependencies deliberately omitted from requirements-ci.txt.
# Smokes that import these are reported as SKIP (not FAIL).
SKIP_ON_MISSING = (
    "chainladder", "lifelib", "solvency2_data", "solvency2-data",
    "sentence_transformers", "sentence-transformers",
    "faiss", "faiss_cpu", "llama_cpp", "llama-cpp-python",
    "playwright",
)


def _missing_dep(stderr: str, stdout: str) -> str:
    """Return the name of the first missing dep, or '' if none."""
    blob = (stderr or "") + "\n" + (stdout or "")
    for line in blob.splitlines():
        if "ModuleNotFoundError" in line or "ImportError" in line:
            for dep in SKIP_ON_MISSING:
                if f"'{dep}'" in line or f'"{dep}"' in line:
                    return dep
    return ""


def _tail3(text: str, width: int = 220) -> str:
    """Last 3 non-empty lines, joined by ' | ', truncated."""
    if not text:
        return ""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    snippet = " | ".join(lines[-3:])
    return snippet[:width]


def run_one(path, timeout, verbose=False):
    t0 = time.time()
    try:
        r = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(ROOT), env=ENV,
        )
        dur = time.time() - t0
        if r.returncode == 0:
            return "PASS", dur, 0, _tail3(r.stdout, 80), r
        dep = _missing_dep(r.stderr or "", r.stdout or "")
        if dep:
            return "SKIP", dur, 0, f"missing optional dep: {dep}", r
        detail = _tail3(r.stdout, 140)
        if r.stderr and r.stderr.strip():
            err = _tail3(r.stderr, 120)
            detail = (detail + "  >> stderr: " + err) if detail else \
                     ("stderr: " + err)
        return "FAIL", dur, r.returncode, detail, r
    except subprocess.TimeoutExpired:
        dur = time.time() - t0
        return "FAIL", dur, "TIMEOUT", f"timed out after {timeout}s", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=90,
                    help="per-smoke timeout in seconds (default 90)")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--verbose", action="store_true",
                    help="dump full stdout/stderr for failed smokes")
    ap.add_argument("--only", nargs="*", default=[],
                    help="run only these part numbers (e.g. 160 161)")
    args = ap.parse_args()

    smokes = find_smokes()

    if args.only:
        wanted = set(args.only)
        def keep(p):
            stem = p.stem
            # smoke_test_part160.py -> "160"
            tag = stem.replace("smoke_test_part", "")
            return tag in wanted
        smokes = [p for p in smokes if keep(p)]

    if args.list:
        for p in smokes:
            print(p.relative_to(ROOT))
        print(f"\n{len(smokes)} smoke(s).")
        return 0

    if not smokes:
        print("[run_all_smokes] no smokes found")
        return 1

    print(f"[run_all_smokes] {len(smokes)} smoke(s), "
          f"timeout={args.timeout}s each")
    print("=" * 66)

    passed = 0
    failed = []
    skipped = []
    t_start = time.time()

    for p in smokes:
        rel = p.relative_to(ROOT)
        mark, dur, rc, tail, res = run_one(p, args.timeout,
                                            verbose=args.verbose)
        print(f"  [{mark}] {str(rel):50s}  {dur:6.2f}s  {tail}")
        if mark == "PASS":
            passed += 1
        elif mark == "SKIP":
            skipped.append((rel, tail))
        else:
            failed.append((rel, rc, tail))
            if args.verbose and res is not None:
                print("      ── full stdout ──")
                for ln in (res.stdout or "").splitlines():
                    print(f"      | {ln}")
                if res.stderr:
                    print("      ── full stderr ──")
                    for ln in res.stderr.splitlines():
                        print(f"      ! {ln}")
                print("      ── end ──")
            if args.fail_fast:
                break

    dur_total = time.time() - t_start
    print("=" * 66)
    print(f"[run_all_smokes] {passed} passed, {len(skipped)} skipped, "
          f"{len(failed)} failed  (of {len(smokes)})  in {dur_total:.1f}s")

    if skipped:
        print("")
        print("SKIPPED (optional deps not installed in CI):")
        for rel, why in skipped:
            print(f"  - {rel}  ({why})")

    if failed:
        print("")
        print("FAILED:")
        for rel, rc, tail in failed:
            print(f"  - {rel}  rc={rc}  {tail}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
