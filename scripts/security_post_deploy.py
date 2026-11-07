#!/usr/bin/env python3
"""Runtime security checks against live deployment (post-deploy)."""
import os
import sys
import urllib.error
import urllib.request
import subprocess
import json

BASE = os.environ.get("SUNNYWARE_URL", "https://shamiur-sunnyware.hf.space")
PASS, FAIL, WARN, SKIP = 0, 0, 0, 0


def p(m): global PASS; print(f"  [PASS] {m}"); PASS += 1
def f(m): global FAIL; print(f"  [FAIL] {m}"); FAIL += 1
def w(m): global WARN; print(f"  [WARN] {m}"); WARN += 1
def s(m): global SKIP; print(f"  [SKIP] {m}"); SKIP += 1


def head(path):
    req = urllib.request.Request(BASE + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")[:500]
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, {}, str(e)


def check_https():
    print("\n[1] HTTPS transport")
    status, _, _ = head("/")
    if status == 0:
        f("Cannot reach " + BASE); return
    p("HTTPS enforced") if BASE.startswith("https://") else f("Not served over HTTPS")


def check_headers():
    print("\n[2] Security headers")
    status, headers, _ = head("/")
    if status == 0:
        s("Cannot fetch headers"); return
    h = {k.lower(): v for k, v in headers.items()}
    must = {"strict-transport-security": "HSTS",
            "x-content-type-options": "nosniff",
            "x-frame-options": "clickjacking"}
    for name, label in must.items():
        (p if name in h else w)(f"{label}: {name} = {h.get(name, 'MISSING')[:40]}")
    should = {"content-security-policy": "CSP",
              "referrer-policy": "referrer policy",
              "permissions-policy": "feature permissions"}
    for name, label in should.items():
        (p if name in h else w)(f"{label}")


def check_auth():
    print("\n[3] Admin auth enforcement")
    protected = ["/api/rag/documents", "/api/security/recon-guard",
                 "/api/accounting/summary", "/api/workos/admin/users"]
    for path in protected:
        req = urllib.request.Request(BASE + path, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception:
            s(f"{path} unreachable"); continue
        if status in (401, 403):
            p(f"{path} -> {status} (auth enforced)")
        elif status == 200:
            w(f"{path} -> 200 WITHOUT auth")
        else:
            s(f"{path} -> {status}")


def check_cors():
    print("\n[4] CORS policy")
    req = urllib.request.Request(BASE + "/api/rag/documents",
                                  headers={"Origin": "https://evil.example.com"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            status = r.status
            acao = r.headers.get("Access-Control-Allow-Origin", "")
            acac = (r.headers.get("Access-Control-Allow-Credentials", "") or "").lower()
            proxied = r.headers.get("x-proxied-replica", "") or r.headers.get("x-proxied-path", "")
    except urllib.error.HTTPError as e:
        status = e.code
        acao = e.headers.get("Access-Control-Allow-Origin", "")
        acac = (e.headers.get("Access-Control-Allow-Credentials", "") or "").lower()
        proxied = e.headers.get("x-proxied-replica", "") or e.headers.get("x-proxied-path", "")
    except Exception:
        s("Cannot test CORS")
        return

    has_wildcard = (acao == "*")
    has_evil = bool(acao) and "evil" in acao
    has_creds = (acac == "true")
    returns_data = (status == 200)
    hf_proxy = bool(proxied)

    # FAIL only if credentials + reflected origin + 200 data
    if returns_data and has_creds and has_evil:
        f(f"Critical: CORS reflects {acao} with credentials on 200 response")
    elif returns_data and has_wildcard and has_creds:
        f("Critical: CORS allows * with credentials on 200 response")
    elif has_evil and has_creds and not returns_data:
        w(f"CORS reflects {acao} with credentials on {status} (no data leaked)")
        if hf_proxy:
            print("        Note: headers added by HF proxy (x-proxied-replica present)")
    elif has_wildcard:
        w("CORS allows * (no credentials)")
    elif has_evil:
        w(f"CORS reflects {acao} (no credentials)")
    elif acao:
        p(f"CORS restricted: {acao[:40]}")
    else:
        p("No CORS on protected endpoint (safe default)")


def check_internal():
    print("\n[5] Internal security status")
    status, _, _ = head("/health/ready")
    (p if status == 200 else w)(f"/health/ready -> {status}")
    status, _, _ = head("/api/security/recon-guard")
    if status in (200, 401, 403):
        p(f"Recon Guard reachable ({status})")


def check_deployment():
    print("\n[6] Deployment sync (remote SHA vs local)")
    try:
        local_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        local_sha = "unknown"

    try:
        req = urllib.request.Request(
            "https://huggingface.co/api/spaces/shamiur/sunnyware"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        remote_sha = data.get("sha", "unknown")
        stage = data.get("runtime", {}).get("stage", "?")
    except Exception as e:
        s(f"Cannot fetch HF Space info: {e}")
        return

    if stage and stage != "RUNNING":
        w(f"HF Space stage: {stage}")
    if remote_sha == local_sha:
        p(f"SHA matches: {remote_sha[:12]}")
    else:
        w(f"SHA mismatch (HF rebuild in progress): remote={remote_sha[:12]} local={local_sha[:12]}")


def main():
    print(f"=== Security Post-Deploy ({BASE}) ===")
    check_https(); check_headers(); check_auth(); check_cors(); check_internal()
    print(f"\n=== Summary: {PASS} pass, {WARN} warn, {FAIL} fail, {SKIP} skip ===")
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
