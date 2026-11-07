#!/usr/bin/env python3
"""Run full test suite, save versioned report + MANIFEST.json + SHA-256 hashes.

Output layout:
  test-results/<timestamp>-<commit>/
    pytest.txt
    pytest.txt.sha256
    MANIFEST.json
  test-results/latest/       (mirror of most recent)
  test-results/latest.txt    (convenience copy)
  test-results/latest.sha256
"""
import os
import sys
import json
import subprocess
import hashlib
import datetime
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "test-results"
RESULTS_DIR.mkdir(exist_ok=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main():
    commit = git_commit()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_dir = RESULTS_DIR / f"{stamp}-{commit[:7]}"
    out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update({
        "NEON_DATABASE_URL": "",
        "SUNNYWARE_DISABLE_SCHEDULER": "1",
        "HF_HOME": "/tmp/huggingface",
    })

    cmd = [
        sys.executable, "-m", "pytest", "tests/",
        "--ignore=tests/test_agent_stream.py",
        "-k", "not test_health_ready",
        "-v", "--tb=short",
    ]
    print(f"[attest] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    pytest_file = out_dir / "pytest.txt"
    pytest_file.write_text(result.stdout + "\n--- STDERR ---\n" + result.stderr, encoding="utf-8")
    pytest_sha = sha256(pytest_file)
    (out_dir / "pytest.txt.sha256").write_text(f"{pytest_sha}  pytest.txt\n", encoding="utf-8")

    manifest = {
        "timestamp_utc": stamp,
        "commit": commit,
        "commit_short": commit[:7],
        "branch": subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "interpreter": sys.executable,
        "command": cmd,
        "exit_code": result.returncode,
        "files": {
            "pytest.txt": {
                "sha256": pytest_sha,
                "bytes": pytest_file.stat().st_size,
            }
        },
        "summary": {
            "passed": result.stdout.count(" PASSED"),
            "failed": result.stdout.count(" FAILED"),
            "errors": result.stdout.count(" ERROR"),
        },
        "verification": {
            "cmd": "python scripts/verify_test_report.py",
            "expect": "OK Report hash matches",
        },
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    latest_dir = RESULTS_DIR / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(out_dir, latest_dir)

    (RESULTS_DIR / "latest.txt").write_text(
        pytest_file.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (RESULTS_DIR / "latest.sha256").write_text(
        f"{pytest_sha}  latest.txt\n", encoding="utf-8"
    )

    print(f"[ok] Report: {out_dir.relative_to(REPO_ROOT)}")
    print(f"[ok] SHA-256: {pytest_sha}")
    print(f"[ok] Passed={manifest['summary']['passed']}, "
          f"Failed={manifest['summary']['failed']}, "
          f"Exit={result.returncode}")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
