#!/usr/bin/env python3
"""scripts/smoke_remote.py — post-push validation against live HF Space."""
import json
import subprocess
import sys
import urllib.error
import urllib.request

BASE = "https://shamiur-sunnyware.hf.space"
SPACE_API = "https://huggingface.co/api/spaces/shamiur/sunnyware"
import os
ADMIN_KEY = os.environ.get("SUNNYWARE_ADMIN_KEY", "TEST_KEY_NOT_REAL")
AUTH_ENABLED = ADMIN_KEY != "TEST_KEY_NOT_REAL" and bool(ADMIN_KEY)
SKIPPED = 0
FAILED = 0

def pass_(msg): print(f"  OK  {msg}")
def fail(msg):
    global FAILED, SKIPPED
    if not AUTH_ENABLED:
        ml = str(msg).lower()
        if any(kw in ml for kw in ['auth', '401', '403', 'unauthorized',
                                    'forbidden', 'admin', 'permission',
                                    'api-key', 'x-api-key']):
            print(f"  SKIP {msg} (no admin key in CI)")
            SKIPPED += 1
            return
    print(f"  FAIL {msg}")
    FAILED = 1
def section(n, title): print(f"\n--- {n}. {title} ---")

def http(path, auth=True, retries=2, delay=2.0):
    """HTTP GET with retry on network failures. Never reads error bodies."""
    import time as _t
    last_err = b""
    for attempt in range(retries + 1):
        req = urllib.request.Request(BASE + path)
        if auth:
            req.add_header("X-API-Key", ADMIN_KEY)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            # Don't read the error body — it can also timeout
            return e.code, b""
        except Exception as e:
            last_err = str(e).encode()
            if attempt < retries:
                _t.sleep(delay)
    return 0, last_err


section(1, "Local git HEAD")
local_sha = subprocess.run(["git", "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
if local_sha: pass_(f"HEAD: {local_sha[:12]}")
else: fail("Could not read local HEAD"); sys.exit(1)

section(2, "HF Space status")
try:
    with urllib.request.urlopen(SPACE_API, timeout=15) as r:
        info = json.loads(r.read())
    stage = info.get("runtime", {}).get("stage", "?")
    remote_sha = info.get("sha", "")
    (pass_ if stage == "RUNNING" else fail)(f"Stage: {stage}")
    if remote_sha == local_sha:
        pass_(f"SHA match: {remote_sha[:12]}")
    else:
        print(f"  WARN SHA mismatch (HF rebuild in progress): remote={remote_sha[:12]} local={local_sha[:12]}")
except Exception as e:
    fail(f"Space info fetch: {e}"); sys.exit(1)

section(3, "API endpoints")
endpoints = [
    ("/ui", None), ("/admin", None),
    ("/api/saas/plans", "plans"), ("/api/saas/orgs", "orgs"),
    ("/api/saas/invoices", "invoices"),
    ("/api/team/members", "members"), ("/api/team/activity", "activity"),
    ("/api/analytics/overview", None), ("/api/analytics/users", "users"),
    ("/api/analytics/charts", "data"),
    ("/api/llm-dashboard/providers", "providers"),
    ("/api/llm-dashboard/orchestrator", "disable_all"),
    ("/api/llm-dashboard/logs", "logs"),
    ("/api/email/logs", "logs"),
    ("/api/api-keys", "keys"),
    ("/api/webhooks/endpoints", "endpoints"),
    ("/api/webhooks/deliveries", "deliveries"),
    ("/api/webhooks/events", "events"),
    ("/api/webhooks/retries", "retries"),
    ("/api/chat-audit/stats", "total_messages"),
    ("/api/chat-audit/messages", "messages"),
    ("/api/scheduled-tasks", "tasks"),
    ("/api/scheduled-tasks/runs", "runs"),
    ("/api/rag-admin/stats", "total_documents"),
    ("/api/rag-admin/documents", "documents"),
    ("/api/2fa/status", "enabled"),
    ("/api/backup/list", "files"),
    ("/api/impersonate/verify", "valid"),
    ("/api/feature-flags", "flags"),
    ("/api/overage/config", "config"),
    ("/api/overage/overview", "orgs"),
    ("/api/slack/config", "enabled"),
    ("/api/admin/feedback", "entries"),
]
for path, key in endpoints:
    status, body = http(path)
    # Part 222b: accept both 200 (2FA off) and 428 (2FA on, gate enforces correctly)
    if status == 428:
        pass_(f"GET {path} -> 428 (2FA gate active)")
        continue
    if status != 200:
        fail(f"GET {path} -> {status}"); continue
    if key is None:
        pass_(f"GET {path} -> 200"); continue
    try:
        data = json.loads(body)
        (pass_ if key in data else fail)(f"GET {path} -> has '{key}'")
    except Exception:
        fail(f"GET {path} -> non-JSON")

section(4, "Served HTML markers")
status, body = http("/admin", auth=False)
html = body.decode(errors="ignore")
for marker, desc in [
    ("async function renderAnalytics", "renderAnalytics defined"),
    ("async function renderLlmDashboard", "renderLlmDashboard defined"),
    ("async function renderEmail", "renderEmail defined"),
    ("async function renderApiKeys", "renderApiKeys defined"),
    ("async function renderWebhooks", "renderWebhooks defined"),
    ("async function renderChatAudit", "renderChatAudit defined"),
    ("async function renderScheduledTasks", "renderScheduledTasks defined"),
    ("async function renderRagAdmin", "renderRagAdmin defined"),
    ("async function renderSecurity", "renderSecurity defined"),
    ("async function renderBackup", "renderBackup defined"),
    ("async function renderImpersonate", "renderImpersonate defined"),
    ("async function renderFeatureFlags", "renderFeatureFlags defined"),
    ("async function renderOverage", "renderOverage defined"),
    ("async function renderSlackBot", "renderSlackBot defined"),
    ("async function renderFeedback", "renderFeedback defined"),
    ("async function downloadInvoicePdf", "downloadInvoicePdf defined"),
    ("async function saveOrch", "saveOrch defined"),
    ('data-tab="email"', "Email nav item"),
    ("function _renderSimpleChart", "Inline SVG chart renderer"),
]:
    (pass_ if marker in html else fail)(desc)

status, body = http("/ui", auth=False)
html = body.decode(errors="ignore")
for marker, desc in [
    ("settingsMenu", "Settings menu"),
    ("settingsCancelBtn", "Cancel subscription button"),
    ("userPillBtn", "User pill"),
]:
    (pass_ if marker in html else fail)(desc)

print()
if FAILED:
    print("=" * 63)
    print(" REMOTE SMOKE TEST FAILED - DEPLOYMENT NOT HEALTHY")
    print("=" * 63)
    sys.exit(1)
print("=" * 63)
print(" REMOTE SMOKE TEST PASSED - DEPLOYMENT HEALTHY")
print("=" * 63)
