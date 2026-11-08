#!/usr/bin/env python3
"""Post-ship deployment verification.

Confirms that what was pushed is byte-identical to what is running on the
remote. Detects:
  - Failed HF Space deploy
  - Corrupted file transfer
  - MITM / cache tampering
  - Stale CDN responses

Compares local reports/latest/MANIFEST.json + reports/CHAIN.json against
what /api/attestation/manifest and /api/attestation/chain return from the
live server.

Exit 0 if everything matches; 1 otherwise.

Appends a timestamped record to reports/DEPLOYMENTS.json for the audit log.
"""
import sys
import json
import time
import argparse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parent.parent
DEFAULT_URL = "https://shamiur-sunnyware.hf.space"
DEPLOYMENTS_PATH = REPO / "reports" / "DEPLOYMENTS.json"

EXPECTED_SCRIPTS = (
    "system_monitor", "pre_push_check", "smoke_local",
    "security_pre_deploy", "smoke_remote",
    "security_post_deploy", "diagnostics",
)


def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "sunnyware-verify-deployed/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_for_deploy(url, expected_version, max_wait=180, interval=10):
    """Poll /api/attestation/manifest until version matches. Return (ok, deployed_version)."""
    deadline = time.time() + max_wait
    last_err = None
    while time.time() < deadline:
        try:
            m = fetch_json(f"{url}/api/attestation/manifest", timeout=5)
            if not isinstance(m, dict):
                raise ValueError("manifest is not a dict")
            if m.get("version") == expected_version:
                return True, expected_version
            last_err = f"version mismatch: remote={m.get('version')} expected={expected_version}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(interval)
    return False, last_err


def compare_manifests(local, remote):
    mismatches = []
    if not isinstance(remote, dict):
        return ["remote manifest is not a dict"]
    for script in EXPECTED_SCRIPTS:
        l = (local.get("reports") or {}).get(script) or {}
        r = (remote.get("reports") or {}).get(script) or {}
        if not r:
            mismatches.append(f"remote missing script: {script}")
            continue
        lh, rh = l.get("sha256", ""), r.get("sha256", "")
        if lh != rh:
            mismatches.append(f"{script}: hash mismatch local={lh[:16]}.. remote={rh[:16]}..")
    return mismatches


def compare_chains(local, remote):
    mismatches = []
    if not isinstance(remote, list):
        return ["remote chain is not a list"]
    if len(remote) < len(local):
        mismatches.append(f"remote chain shorter: {len(remote)} < {len(local)}")
        return mismatches
    for i, block in enumerate(local):
        rblock = remote[i]
        for field in ("block_hash", "prev_block_hash", "combined_hash"):
            lb, rb = block.get(field, ""), rblock.get(field, "")
            if lb != rb:
                mismatches.append(f"block {i} {field}: local={lb[:16]}.. remote={rb[:16]}..")
    return mismatches


def append_deployment(record):
    deployments = []
    if DEPLOYMENTS_PATH.exists():
        try:
            deployments = json.loads(DEPLOYMENTS_PATH.read_text(encoding="utf-8"))
            if not isinstance(deployments, list):
                deployments = []
        except Exception:
            deployments = []
    deployments.append(record)
    DEPLOYMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEPLOYMENTS_PATH.write_text(json.dumps(deployments, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="remote base URL")
    parser.add_argument("--wait", type=int, default=180, help="max seconds to wait for deploy (default 180)")
    parser.add_argument("--skip-wait", action="store_true", help="don't poll for deploy readiness")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    url = args.url.rstrip("/")
    local_chain = json.loads((REPO / "reports" / "CHAIN.json").read_text(encoding="utf-8"))
    local_manifest = json.loads((REPO / "reports" / "latest" / "MANIFEST.json").read_text(encoding="utf-8"))
    expected_version = local_manifest.get("version")
    latest_block_idx = len(local_chain) - 1
    latest_block_hash = local_chain[-1]["block_hash"] if local_chain else "0" * 64

    if not args.json:
        print(f"[verify] remote:  {url}")
        print(f"[verify] version: {expected_version}")
        print(f"[verify] chain:   {len(local_chain)} blocks, head {latest_block_hash[:16]}...")

    def _record(verified, deployed_version, error, mismatches):
        return {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "remote_url": url,
            "chain_block": latest_block_idx,
            "chain_hash": latest_block_hash,
            "expected_version": expected_version,
            "deployed_version": deployed_version,
            "verified": verified,
            "error": error,
            "mismatches": mismatches,
        }

    # 1. Wait for deploy
    if not args.skip_wait:
        if not args.json:
            print(f"[verify] polling for {expected_version} (max {args.wait}s)...")
        ok, info = wait_for_deploy(url, expected_version, max_wait=args.wait)
        if not ok:
            result = _record(False, None, f"deploy not ready: {info}", [])
            append_deployment(result)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"[FAIL] {info}")
            return 1
        if not args.json:
            print(f"[verify] deployed version confirmed: {info}")

    # 2. Fetch remote artifacts
    try:
        remote_manifest = fetch_json(f"{url}/api/attestation/manifest")
        remote_chain = fetch_json(f"{url}/api/attestation/chain")
    except Exception as e:
        result = _record(False, None, f"fetch failed: {type(e).__name__}: {e}", [])
        append_deployment(result)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"[FAIL] couldn't fetch remote artifacts: {e}")
        return 1

    # 3. Compare
    mismatches = compare_manifests(local_manifest, remote_manifest) + \
                 compare_chains(local_chain, remote_chain)
    verified = len(mismatches) == 0
    deployed_version = remote_manifest.get("version") if isinstance(remote_manifest, dict) else None
    result = _record(verified, deployed_version, None, mismatches)
    append_deployment(result)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if verified:
            print(f"[PASS] remote matches local — {len(local_chain)} blocks, "
                  f"{len(EXPECTED_SCRIPTS)} hashes all match")
        else:
            print(f"[FAIL] {len(mismatches)} mismatch(es):")
            for m in mismatches:
                print(f"  - {m}")

    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
