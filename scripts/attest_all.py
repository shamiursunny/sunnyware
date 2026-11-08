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
    ("diagnostics", ["scripts/diagnostics.py", "--attest"],
     "Automatic error detection: registry/schema integrity, recursive-name guard"),
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
        f"Every commit ships {len(manifest['reports'])} **tamper-evident** quality reports.",
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

    # Blockchain hash ladder — append block linking to previous run
    try:
        import hash_chain
        manifest = hash_chain.append_block(manifest)
        block = manifest.get("chain", {})
        if block:
            print(f"[chain] block #{block.get('index')} {block.get('block_hash', '')[:16]}...")
    except Exception as e:
        print(f"[chain] warning: {type(e).__name__}: {e}")

    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    latest = REPORTS / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(out_dir, latest)

    print(f"[ok] reports -> {out_dir.relative_to(REPO)}")
    update_readme(manifest)
    update_readme_chain()
    update_readme_deployments()

    # Use normalized_exit so system_monitor exit 2 counts as warning, not failure
    if any(manifest["reports"][n].get("normalized_exit", manifest["reports"][n]["exit_code"]) != 0
           for n in CRITICAL if n in manifest["reports"]):
        return 1
    return 0


def update_readme_chain():
    """Auto-update the blockchain section in README from CHAIN.json.

    Enterprise-grade trust section — regenerated on every attestation run.
    This is the source of truth for third-party auditors verifying the chain.
    """
    try:
        import hash_chain
        chain = hash_chain.load_chain()
        readme_path = REPO / "README.md"
        if not readme_path.exists():
            return
        text = readme_path.read_text(encoding="utf-8")

        if not chain:
            content_body = "_No attestation runs have been chained yet._\n"
            length = 0
        else:
            latest = chain[-1]
            length = len(chain)
            rows = []
            for blk in reversed(chain):
                idx = blk.get("index", "?")
                bh = (blk.get("block_hash") or "")[:16] + "..."
                ph = (blk.get("prev_block_hash") or "")[:16] + "..."
                cm = blk.get("commit", "")
                ver = blk.get("version", "")
                ts = blk.get("timestamp_utc", "")
                rows.append(f"| {idx} | `{bh}` | `{ph}` | `{cm}` | {ver} | {ts} |")
            table = "\n".join(rows)
            content_body = (
                "### Trust Summary\n\n"
                "| Property | Value |\n"
                "|----------|-------|\n"
                f"| **Chain length** | {length} blocks |\n"
                f"| **Latest block hash** | `{latest.get('block_hash', '')}` |\n"
                f"| **Latest commit** | `{latest.get('commit', '')}` |\n"
                f"| **Latest version** | {latest.get('version', '')} |\n"
                f"| **Genesis hash** | `{'0'*64}` |\n\n"
                "### Full Blockchain\n\n"
                "| # | Block Hash | Prev Hash | Commit | Version | Timestamp (UTC) |\n"
                "|---|-----------|-----------|--------|---------|-----------------|\n"
                f"{table}\n"
            )

        block = (
            "## ⛓️ Attestation Blockchain (Enterprise Trust Chain)\n\n"
            "_Auto-generated by `scripts/attest_all.py` on every ship. Do not edit manually._\n\n"
            "<!-- CHAIN:START -->\n"
            f"{content_body}\n"
            "### Security Properties\n\n"
            "- **Tamper-evident** — modifying any historical report or block breaks all subsequent hashes\n"
            "- **Append-only** — blocks cannot be inserted or reordered without breaking the chain\n"
            "- **Deterministic** — `diagnostics --attest` produces byte-identical output across runs\n"
            "- **Idempotent** — re-running attestation on unchanged code does not create duplicate blocks\n\n"
            "### Verification (Source of Truth)\n\n"
            "```bash\n"
            "python scripts/verify_chain.py           # verify full chain integrity\n"
            "python scripts/verify_attestations.py    # verify individual report hashes\n"
            "cat reports/CHAIN.json | python -m json.tool  # inspect raw chain\n"
            "```\n\n"
            "### Trust Model\n\n"
            "**Cryptographically guaranteed:**\n"
            "1. Every shipped version was attested by all 7 independent scripts\n"
            "2. Each attestation run is linked to its predecessor via SHA-256\n"
            "3. Historical reports cannot be silently rewritten without breaking the chain\n"
            "4. Anyone can independently verify the chain from `reports/CHAIN.json`\n\n"
            "**Not guaranteed:**\n"
            "- Absence of bugs (certifies process integrity, not code perfection)\n"
            "- Maintainer trustworthiness (chain records what was signed, not whether it should be trusted)\n\n"
            "<!-- CHAIN:END -->\n"
        )

        start_marker = "<!-- CHAIN:START -->"
        end_marker = "<!-- CHAIN:END -->"
        if start_marker in text and end_marker in text:
            start_idx = text.find(start_marker)
            header_idx = text.rfind("## ⛓️ Attestation Blockchain", 0, start_idx)
            if header_idx > 0:
                start_idx = header_idx
            end_idx = text.find(end_marker) + len(end_marker)
            text = text[:start_idx] + block + text[end_idx:]
        else:
            anchor = "## Automatic Error Detection (Diagnostics)"
            if anchor in text:
                text = text.replace(anchor, block + "\n" + anchor, 1)
            elif "<!-- ATTESTATIONS:END -->" in text:
                text = text.replace(
                    "<!-- ATTESTATIONS:END -->",
                    "<!-- ATTESTATIONS:END -->\n\n" + block,
                    1,
                )
            else:
                text = text.rstrip() + "\n\n" + block

        readme_path.write_text(text, encoding="utf-8")
        print(f"[chain] README updated ({length} blocks)")
    except Exception as e:
        print(f"[chain] README update warning: {type(e).__name__}: {e}")


def update_readme_deployments():
    """Auto-update Deployment Trust Log in README from DEPLOYMENTS.json."""
    try:
        deployments_path = REPO / "reports" / "DEPLOYMENTS.json"
        readme_path = REPO / "README.md"
        if not readme_path.exists():
            return

        deployments = []
        if deployments_path.exists():
            try:
                deployments = json.loads(deployments_path.read_text(encoding="utf-8"))
                if not isinstance(deployments, list):
                    deployments = []
            except Exception:
                deployments = []

        text = readme_path.read_text(encoding="utf-8")

        if not deployments:
            content_body = "_No post-ship verifications recorded yet._\n"
        else:
            verified_count = sum(1 for d in deployments if d.get("verified"))
            rows = []
            for d in reversed(deployments[-20:]):
                status = "PASS" if d.get("verified") else "FAIL"
                blk = d.get("chain_block", "?")
                ver = d.get("deployed_version") or "?"
                cm = (d.get("chain_hash") or "")[:16] + "..."
                ts = d.get("timestamp_utc", "")
                rows.append(f"| {ts} | v{ver} | #{blk} | `{cm}` | {status} |")
            table = "\n".join(rows)
            content_body = (
                f"**{verified_count}/{len(deployments)} deployments verified**\n\n"
                "| Timestamp (UTC) | Version | Block | Chain Hash | Result |\n"
                "|-----------------|---------|-------|------------|--------|\n"
                f"{table}\n"
            )

        block = (
            "## \U0001F680 Deployment Trust Log\n\n"
            "_Auto-generated by `scripts/attest_all.py` from `reports/DEPLOYMENTS.json`. Do not edit manually._\n\n"
            "<!-- DEPLOYMENTS:START -->\n"
            f"{content_body}\n"
            "### What this proves\n\n"
            "- Each entry was created **after** the HF Space reported the same version\n"
            "- Every script hash on the server was compared to the local chain\n"
            "- Every blockchain block was compared to the local chain\n"
            "- Tampering with either the server or the repo breaks the comparison\n\n"
            "### Verification command\n\n"
            "```bash\n"
            "python scripts/verify_deployed.py --skip-wait   # compare current state\n"
            "```\n\n"
            "<!-- DEPLOYMENTS:END -->\n"
        )

        start_marker = "<!-- DEPLOYMENTS:START -->"
        end_marker = "<!-- DEPLOYMENTS:END -->"
        if start_marker in text and end_marker in text:
            start_idx = text.find(start_marker)
            header_idx = text.rfind("## \U0001F680 Deployment Trust Log", 0, start_idx)
            if header_idx > 0:
                start_idx = header_idx
            end_idx = text.find(end_marker) + len(end_marker)
            text = text[:start_idx] + block + text[end_idx:]
        else:
            chain_end = "<!-- CHAIN:END -->"
            if chain_end in text:
                text = text.replace(chain_end, chain_end + "\n\n" + block, 1)
            else:
                text = text.rstrip() + "\n\n" + block

        readme_path.write_text(text, encoding="utf-8")
        print(f"[deploy] README updated ({len(deployments)} deployment(s))")
    except Exception as e:
        print(f"[deploy] README update warning: {type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())
