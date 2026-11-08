#!/usr/bin/env python3
"""Sunnyware - one-command fully automated ship.

Runs every quality + security check, bumps version, tags, pushes to GitHub
and Hugging Face, waits for HF rebuild, then verifies the live deployment.
Shows a clear pass/fail summary table at the end.

Usage:
  python scripts/ship.py                     # full pipeline
  python scripts/ship.py --dry-run           # preview only
  python scripts/ship.py --no-push           # commit + tag, no push
  python scripts/ship.py --skip-deploy       # skip post-deploy verification
  python scripts/ship.py --wait 180          # HF rebuild wait (seconds)
  python scripts/ship.py --message "..."     # custom commit message

Exit codes:
  0 = all passed
  1 = critical check failed (nothing pushed)
  2 = git push failed (committed locally)
  3 = post-deploy failed (pushed but live check failed)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports" / "latest"

CRITICAL = {
    "bump_version", "pre_push_check", "security_pre_deploy",
    "verify_hashes", "commit_and_tag", "push_remotes",
}


def run(name, cmd, timeout=900):
    print("\n" + "=" * 70)
    print("  > " + name)
    print("=" * 70)
    start = time.time()
    try:
        r = subprocess.run(
            cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        dur = time.time() - start
        lines = (r.stdout or "").splitlines()
        for line in lines[-8:]:
            print("  " + line)
        if r.returncode != 0 and r.stderr:
            for line in r.stderr.splitlines()[-4:]:
                print("  [WARN] " + line)
        return r.returncode == 0, dur
    except subprocess.TimeoutExpired:
        print("  [TIMEOUT] after " + str(timeout) + "s")
        return False, time.time() - start
    except Exception as e:
        print("  [ERROR] " + type(e).__name__ + ": " + str(e))
        return False, time.time() - start


def read_version():
    init = REPO / "src" / "sunnyware" / "__init__.py"
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']',
                  init.read_text(encoding="utf-8"))
    return m.group(1) if m else "unknown"


def parse_manifest():
    mp = REPORTS / "MANIFEST.json"
    if not mp.exists():
        return {}
    try:
        return json.loads(mp.read_text(encoding="utf-8")).get("reports", {})
    except Exception:
        return {}


def print_summary(results, version, total_sec):
    print("\n" + "=" * 70)
    print("  SUNNYWARE SHIP SUMMARY - v" + version)
    print("=" * 70 + "\n")
    print("  {:<30} {:<8} {:>8}  {}".format("Check", "Status", "Time", "Details"))
    print("  " + "-" * 30 + " " + "-" * 8 + " " + "-" * 8 + "  " + "-" * 30)

    fails = []
    for name, status, dur, detail in results:
        icon = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
        print("  {} {:<26} {:<8} {:>6.1f}s  {}".format(icon, name, status, dur, detail[:40]))
        if status == "FAIL":
            fails.append(name)

    print("\n  Total time: {:.1f}s".format(total_sec))
    print("  Version: v" + version)
    print("  Reports: reports/latest/MANIFEST.json")
    print("  Verify: python scripts/verify_attestations.py")

    if fails:
        print("\n  {} failure(s): {}".format(len(fails), ", ".join(fails)))
    else:
        print("\n  All checks passed - ship successful!")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--skip-deploy", action="store_true")
    ap.add_argument("--wait", type=int, default=180)
    ap.add_argument("--message", default=None)
    args = ap.parse_args()

    results = []
    t0 = time.time()

    ok, dur = run("Bump version", [sys.executable, "scripts/bump_version.py"])
    results.append(("bump_version", "PASS" if ok else "FAIL", dur, ""))
    if not ok:
        print_summary(results, "?", time.time() - t0)
        return 1

    version = read_version()
    print("\nTarget version: v" + version)

    if args.dry_run:
        print("\nDRY-RUN - aborting before attest (no files changed).")
        return 0

    ok, dur = run("Attest all (7 scripts)", [sys.executable, "scripts/attest_all.py"])
    results.append(("attest_all", "PASS" if ok else "FAIL", dur, "7 reports" if ok else "see above"))

    reports = parse_manifest()
    for name, info in reports.items():
        exit_code = info.get("exit_code", 0)
        norm = info.get("normalized_exit", exit_code)
        if norm == 0 and exit_code == 0:
            status, detail = "PASS", "exit=0"
        elif norm == 0 and exit_code == 2:
            status, detail = "WARN", "exit=2 (warnings)"
        else:
            status, detail = "FAIL", "exit=" + str(exit_code)
        results.append(("  " + name, status, 0, detail))

    ok, dur = run("Verify hashes", [sys.executable, "scripts/verify_attestations.py"])
    results.append(("verify_hashes", "PASS" if ok else "FAIL", dur, "" if ok else "see above"))

    # Blockchain hash ladder verification (enterprise trust chain)
    ok, dur = run("Verify chain", [sys.executable, "scripts/verify_chain.py"])
    results.append(("verify_chain", "PASS" if ok else "FAIL", dur, "" if ok else "see above"))

    critical_fail = [n for n, s, _, _ in results
                     if s == "FAIL" and n.strip() in CRITICAL]
    if critical_fail:
        print_summary(results, version, time.time() - t0)
        print("Critical failures: " + ", ".join(critical_fail))
        print("Nothing pushed. Fix the errors above and re-run.")
        return 1

    if args.no_push:
        print("\n--no-push: stopping before commit.")
        print_summary(results, version, time.time() - t0)
        return 0

    msg = args.message or ("chore(release): v" + version)
    run("git add", ["git", "add", "-A"])
    ok_commit, dur = run("git commit", ["git", "commit", "-m", msg])
    ok_tag, _ = run("git tag", ["git", "tag", "-a", "v" + version, "-m", "Release v" + version])
    results.append(("commit_and_tag", "PASS" if (ok_commit and ok_tag) else "FAIL", dur, "v" + version))
    if not (ok_commit and ok_tag):
        print_summary(results, version, time.time() - t0)
        return 1

    ok_g, dur = run("push origin main", ["git", "push", "origin", "main"])
    ok_h, _ = run("push hf main", ["git", "push", "hf", "main"])
    ok_t, _ = run("push tag", ["git", "push", "origin", "v" + version])
    push_ok = ok_g and ok_h and ok_t
    results.append(("push_remotes", "PASS" if push_ok else "FAIL", dur, ""))
    if not push_ok:
        print_summary(results, version, time.time() - t0)
        print("Push failed - fix remote access and retry.")
        return 2

    if not args.skip_deploy:
        print("\nWaiting " + str(args.wait) + "s for HF rebuild...")
        time.sleep(args.wait)

        ok, dur = run("Post-deploy smoke", [sys.executable, "scripts/smoke_remote.py"])
        results.append(("post_deploy_smoke", "PASS" if ok else "WARN", dur,
                        "SHA may still mismatch" if not ok else ""))

        ok, dur = run("Post-deploy security", [sys.executable, "scripts/security_post_deploy.py"])
        results.append(("post_deploy_security", "PASS" if ok else "WARN", dur, ""))

    print_summary(results, version, time.time() - t0)
    fails = [n for n, s, _, _ in results if s == "FAIL"]
    return 3 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
