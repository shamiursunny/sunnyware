#!/usr/bin/env python3
"""scripts/smoke_local.py — pre-push validation."""
import os
import re
import subprocess
import sys
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)
FAILED = 0

def pass_(msg): print(f"  OK  {msg}")
def fail(msg):
    global FAILED
    print(f"  FAIL {msg}")
    FAILED = 1
def section(n, title): print(f"\n--- {n}. {title} ---")

# 1. Python compilation
section(1, "Python compilation")
py_files = [
    "src/sunnyware/main.py",
    "src/sunnyware/analytics_store.py",
    "src/sunnyware/analytics_hooks.py",
    "src/sunnyware/llm_dashboard_store.py",
    "src/sunnyware/email_store.py",
    "src/sunnyware/api_keys_store.py",
    "src/sunnyware/chat_audit_store.py",
    "src/sunnyware/rag_admin_store.py",
    "src/sunnyware/twofa_store.py",
    "src/sunnyware/scheduled_tasks_store.py",
    "src/sunnyware/webhooks_store.py",
    "src/sunnyware/team_store.py",
    "src/sunnyware/invoice_pdf.py",
    "src/sunnyware/routes/analytics.py",
    "src/sunnyware/routes/llm_dashboard.py",
    "src/sunnyware/routes/team.py",
    "src/sunnyware/routes/email.py",
    "src/sunnyware/routes/api_keys.py",
    "src/sunnyware/routes/chat_audit.py",
    "src/sunnyware/routes/rag_admin.py",
    "src/sunnyware/routes/twofa.py",
    "src/sunnyware/routes/backup.py",
    "src/sunnyware/impersonation_store.py",
    "src/sunnyware/routes/impersonation.py",
    "src/sunnyware/feature_flags_store.py",
    "src/sunnyware/routes/feature_flags.py",
    "src/sunnyware/overage_store.py",
    "src/sunnyware/routes/overage.py",
    "src/sunnyware/slack_store.py",
    "src/sunnyware/routes/slack_bot.py",
    "src/sunnyware/routes/scheduled_tasks.py",
    "src/sunnyware/routes/webhooks.py",
    "src/sunnyware/routes/agent.py",
    "src/sunnyware/routes/saas.py",
    "src/sunnyware/routes/auth.py",
    "src/sunnyware/routes/authkit.py",
]
all_ok = True
for f in py_files:
    if not Path(f).exists():
        fail(f"missing {f}"); all_ok = False; continue
    r = subprocess.run([sys.executable, "-m", "py_compile", f], capture_output=True)
    if r.returncode != 0:
        fail(f"{f}: {r.stderr.decode(errors='ignore')[:200]}")
        all_ok = False
if all_ok: pass_(f"All {len(py_files)} files compile")

# 2. Routes registered in main.py
section(2, "Route registration in main.py")
main = Path("src/sunnyware/main.py").read_text(encoding="utf-8")
for imp in ["analytics as analytics_routes", "llm_dashboard as llm_dashboard_routes",
            "team as team_routes", "email as email_routes",
            "api_keys as api_keys_routes", "webhooks as webhooks_routes",
            "chat_audit as chat_audit_routes", "scheduled_tasks as scheduled_tasks_routes",
            "rag_admin as rag_admin_routes",
            "twofa as twofa_routes",
            "backup as backup_routes",
            "impersonation as impersonation_routes",
            "feature_flags as feature_flags_routes",
            "overage as overage_routes",
            "slack_bot as slack_bot_routes"]:
    (pass_ if imp in main else fail)(f"import: {imp}")
for inc in ["analytics_routes.router", "llm_dashboard_routes.router",
            "team_routes.router", "email_routes.router",
            "api_keys_routes.router", "webhooks_routes.router",
            "chat_audit_routes.router", "scheduled_tasks_routes.router",
            "rag_admin_routes.router",
            "twofa_routes.router",
            "backup_routes.router",
            "impersonation_routes.router",
            "feature_flags_routes.router",
            "overage_routes.router",
            "slack_bot_routes.router"]:
    (pass_ if f"include_router({inc})" in main else fail)(f"include_router({inc})")

# 3. JS syntax
section(3, "JavaScript syntax")
for html_file in ["static/chat.html", "static/admin-v2.html"]:
    html = Path(html_file).read_text(encoding="utf-8")
    m = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    if not m: fail(f"{html_file}: no inline <script>"); continue
    import tempfile
    tmp = str(Path(tempfile.gettempdir()) / "_smoke_test.js")
    Path(tmp).write_text(m.group(1), encoding="utf-8")
    r = subprocess.run(["node", "--check", tmp], capture_output=True)
    (pass_ if r.returncode == 0 else fail)(f"{html_file}: syntax")

# 4. Critical UI markers
section(4, "Critical UI markers")
chat = Path("static/chat.html").read_text(encoding="utf-8")
admin = Path("static/admin-v2.html").read_text(encoding="utf-8")

cdns_ok = (admin.find("chart.js@3") >= 0 and admin.find("chart.js@3") < admin.find("</head>"))
checks = [
    ("chat.html has settings menu", 'id="settingsMenu"' in chat),
    ("chat.html has user pill", 'id="userPillBtn"' in chat),
    ("chat.html has cancel button", 'id="settingsCancelBtn"' in chat),
    ("chat.html has applyTheme", "applyTheme" in chat),
    ("chat.html has impersonation banner", "impersonation-banner" in chat),
    ("chat.html has stopImpersonation function", "async function stopImpersonation" in chat),
    ("admin-v2.html has _renderSimpleChart", "function _renderSimpleChart" in admin),
    ("admin-v2.html has renderAnalytics", "async function renderAnalytics" in admin),
    ("admin-v2.html has renderLlmDashboard", "async function renderLlmDashboard" in admin),
    ("admin-v2.html has renderEmail", "async function renderEmail" in admin),
    ("admin-v2.html has renderApiKeys", "async function renderApiKeys" in admin),
    ("admin-v2.html has renderChatAudit", "async function renderChatAudit" in admin),
    ("admin-v2.html has renderScheduledTasks", "async function renderScheduledTasks" in admin),
    ("admin-v2.html has renderRagAdmin", "async function renderRagAdmin" in admin),
    ("admin-v2.html has renderSecurity", "async function renderSecurity" in admin),
    ("admin-v2.html has renderBackup", "async function renderBackup" in admin),
    ("admin-v2.html has renderImpersonate", "async function renderImpersonate" in admin),
    ("admin-v2.html has renderFeatureFlags", "async function renderFeatureFlags" in admin),
    ("admin-v2.html has renderOverage", "async function renderOverage" in admin),
    ("admin-v2.html has renderSlackBot", "async function renderSlackBot" in admin),
    ("admin-v2.html has renderWebhooks", "async function renderWebhooks" in admin),
    ("admin-v2.html has downloadInvoicePdf", "async function downloadInvoicePdf" in admin),
    ("admin-v2.html has saveOrch", "async function saveOrch" in admin),
    ("admin-v2.html has analytics nav", 'data-tab="analytics"' in admin),
    ("admin-v2.html has llm-dashboard nav", 'data-tab="llm-dashboard"' in admin),
    ("admin-v2.html has email nav", 'data-tab="email"' in admin),
    ("admin-v2.html has sendPromoEmail", "async function sendPromoEmail" in admin),
]
for msg, ok in checks:
    (pass_ if ok else fail)(msg)

# 5. Result
print()
if FAILED:
    print("=" * 63)
    print(" LOCAL SMOKE TEST FAILED - DO NOT PUSH")
    print("=" * 63)
    sys.exit(1)
print("=" * 63)
print(" LOCAL SMOKE TEST PASSED - READY TO PUSH")
print("=" * 63)
