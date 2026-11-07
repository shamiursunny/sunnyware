#!/usr/bin/env python3
"""One-command test runner: tests + attestation + verify + optional publish.

Usage:
  python run_tests.py            # local, no commit
  python run_tests.py --publish  # also commit + push
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent


def sh(cmd, **kw):
    print(f"[run] {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, cwd=REPO, **kw)


def main():
    publish = "--publish" in sys.argv

    rc = sh([sys.executable, "scripts/generate_test_report.py"]).returncode
    if rc != 0:
        print("[fail] Tests failed - not publishing")
        return rc

    rc = sh([sys.executable, "scripts/verify_test_report.py"]).returncode
    if rc != 0:
        print("[fail] Hash verification failed")
        return rc

    print("[ok] Tests passed, hash verified")

    if publish:
        sh(["git", "add", "test-results/"])
        sh(["git", "commit", "-m", "CI: publish test attestation [skip ci]"])
        sh(["git", "push", "origin", "main"])
        sh(["git", "push", "hf", "main"])
        print("[ok] Published to GitHub + Hugging Face")

    return 0


if __name__ == "__main__":
    sys.exit(main())
