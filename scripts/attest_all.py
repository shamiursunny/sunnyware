#!/usr/bin/env python3
"""Run all quality + security scripts, hash output, update README, generate MANIFEST."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / "reports"
README = REPO / "README.md"
M_START = "<!-- ATTESTATIONS:START -->"
M_END = "<!-- ATTESTATIONS:END -->"

SCRIPTS = [
    ("system_monitor",  ["scripts/system_monitor.py", "--offline"],
     "Full system health + 54 production checks"),
    ("pre_push_check",  ["scripts/pre_push_check.py"],
     "Pre-push gate: syntax, HTML sanity, smoke test"),
    ("smoke_local",     ["scripts/smoke_local.py"],
     "Local HTML/structure validation"),
    ("security_pre_deploy", ["scripts/security_pre_deploy.py"],
     "Static security: secrets, imports, CVEs, bandit"),
    ("smoke_remote",    ["scripts/smoke_remote.py"],
     "Live HF Space deployment health"),
    ("security_post_deploy", ["scripts/security_post_deploy.py"],
     "Runtime security: headers, auth, CORS"),
]

CRITICAL = {"system_monitor", "pre_push_check", "security_pre_deploy"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except Exception:
        return "unknown"


def run(cmd, timeout=300):
    env = os.environ.copy()
    env.update({
        "NEON_DATABASE_URL": "",
        "SUNNYWARE_DISABLE_SCHEDULER": "1",
        "SUNNYWARE_ADMIN_KEY": "",
        "SUNNYWARE_DATA_DIR": tempfile.gettempdir() + "/sunnyware",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    try:
        r = subprocess.run(
            [sys.executable] + cmd, cwd=REPO,
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return r.returncode, r.stdout + "\n--- STDERR ---\n" + r.stderr
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT after {timeout}s"
    except Exception as e:
        return -2, f"ERROR: {type(e).__name__}: {e}"


def update_readme(manifest):
    if not README.exists():
        return
    t = README.read_text(encoding="utf-8")
    if M_START not in t or M_END not in t:
        print("[skip] README markers missing")
        return

    blurbs = dict((n, b) for n, _, b in SCRIPTS)
    lines = [
        "",
        "## Verifiable Quality Reports",
        "",
        f"**Version:** `v{manifest.get('version', 'unknown')}` · "
        f"**Commit:** `{manifest['commit_short']}` · "
        f"**Generated:** `{manifest['timestamp_utc']}`",
        "",
        "Every commit ships six **tamper-evident** quality reports.",
        "",
        "| Report | Exit | SHA-256 (first 16) | What it proves |",
        "|---|---|---|---|",
    ]
    for name, info in manifest["reports"].items():
        norm = info.get("normalized_exit", info["exit_code"])
        if norm == 0 and info["exit_code"] == 0:
            icon = "✅"
        elif norm == 0 and info["exit_code"] == 2:
            icon = "⚠️"
        else:
            icon = "❌"
        lines.append(
            f"| `{name}` | {icon} {info['exit_code']} | "
            f"`{info['sha256'][:16]}…` | {blurbs.get(name, '')} |"
        )
    lines += [
        "",
        "**Verify integrity in 1 second:**",
        "```bash",
        "python scripts/verify_attestations.py",
        "```",
        "",
        "Full reports + hashes: [`reports/latest/MANIFEST.json`](./reports/latest/MANIFEST.json). "
        "Each report is timestamped and linked to this git commit — anyone can re-run and reproduce.",
        "",
    ]
    new_block = M_START + "\n" + "\n".join(lines) + "\n" + M_END
    t = re.sub(
        re.escape(M_START) + r".*?" + re.escape(M_END),
        new_block, t, flags=re.DOTALL,
    )
    README.write_text(t, encoding="utf-8")
    print("[ok] README attestation table updated")


def main():
    # If --bump flag is passed, bump the version first
    if "--bump" in sys.argv:
        import subprocess as _sub
        r = _sub.run(
            [sys.executable, "scripts/bump_version.py"],
            cwd=REPO, capture_output=True, text=True,
        )
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr)
            return r.returncode

    # Read current version for manifest + README
    import re as _re2
    _init_path = REPO / "src" / "sunnyware" / "__init__.py"
    _ver_match = _re2.search(
        r'__version__\s*=\s*["\']([^"\']+)["\']',
        _init_path.read_text(encoding="utf-8"),
    )
    version = _ver_match.group(1) if _ver_match else "unknown"

    commit = git_commit()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_dir = REPORTS / f"{stamp}-{commit[:7]}"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "timestamp_utc": stamp,
        "commit": commit,
        "commit_short": commit[:7],
        "version": version,
        "reports": {},
    }

    for name, cmd, _ in SCRIPTS:
        print(f"[attest] {name} ...", flush=True)
        rc, output = run(cmd)
        f = out_dir / f"{name}.txt"
        f.write_text(output, encoding="utf-8")
        h = sha256_file(f)
        (out_dir / f"{name}.txt.sha256").write_text(f"{h}  {name}.txt\n", encoding="utf-8")
        # For system_monitor, exit 2 means "usable with non-critical warnings" → acceptable
        normalized_rc = 0 if (name == "system_monitor" and rc == 2) else rc
        manifest["reports"][name] = {
            "exit_code": rc, "normalized_exit": normalized_rc,
            "sha256": h, "bytes": f.stat().st_size, "file": f"{name}.txt",
        }
        print(f"  exit={rc}{' (treating as warning)' if normalized_rc == 0 and rc != 0 else ''} sha256={h[:16]}...")

    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    latest = REPORTS / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(out_dir, latest)

    print(f"[ok] reports -> {out_dir.relative_to(REPO)}")
    update_readme(manifest)

    # Use normalized_exit so system_monitor exit 2 counts as warning, not failure
    if any(manifest["reports"][n].get("normalized_exit", manifest["reports"][n]["exit_code"]) != 0
           for n in CRITICAL if n in manifest["reports"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
