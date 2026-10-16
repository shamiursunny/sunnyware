#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 40 smoke test - token usage dashboard."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

PASS = 0
FAIL = 0


def check(name, ok):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  [PASS] " + name)
    else:
        FAIL += 1
        print("  [FAIL] " + name)


def main():
    print("=" * 60)
    print(" Part 40 smoke test - token usage dashboard")
    print("=" * 60)
    print()

    try:
        from sunnyware import webui
    except Exception as e:
        print("[FAIL] cannot import webui: " + type(e).__name__ + ": " + str(e))
        return 1

    html = webui.HTML

    print("DOM markers:")
    check("usageBtn button",       'id="usageBtn"' in html)
    check("usageModal overlay",    'id="usageModal"' in html)
    check("usageClose button",     'id="usageClose"' in html)
    check("usageBody container",   'id="usageBody"' in html)

    print()
    print("CSS markers:")
    check(".modal-overlay",        ".modal-overlay {" in html)
    check(".modal-panel",          ".modal-panel {" in html)
    check(".usage-grid",           ".usage-grid {" in html)
    check(".usage-card",           ".usage-card {" in html)
    check(".usage-table",          ".usage-table {" in html)
    check(".icon-btn-wide",        ".icon-btn-wide {" in html)

    print()
    print("JS functions:")
    check("openUsageModal",        "async function openUsageModal" in html)
    check("closeUsageModal",       "function closeUsageModal" in html)
    check("renderUsageDashboard",  "function renderUsageDashboard" in html)
    check("fmtNum helper",         "function fmtNum" in html)
    check("addUsageCard helper",   "function addUsageCard" in html)
    check("addTableCell helper",   "function addTableCell" in html)

    print()
    print("JS wiring:")
    check("usageBtn wired",        "usageBtn.addEventListener" in html)
    check("usageClose wired",      "usageClose.addEventListener" in html)
    check("backdrop click close",  "e.target === usageModal" in html)
    check("uses /api/usage",       "/api/usage" in html)
    check("uses /api/usage/pricing", "/api/usage/pricing" in html)

    print()
    print("Escaping sanity (no raw newlines in JS single-quoted strings):")
    BS = chr(92)
    bad_patterns = [chr(39) + chr(10) + "     ", chr(39) + chr(10) + "  "]
    present_bad = [p for p in bad_patterns if p in html]
    check("no raw newlines in JS strings", len(present_bad) == 0)

    print()
    print("Structure preserved:")
    check("sidebar intact",        'id="sidebar"' in html)
    check("chat div intact",       'id="chat"' in html)
    check("sendMessage present",   "async function sendMessage" in html)
    check("newChatBtn intact",     'id="newChatBtn"' in html)

    print()
    print("=" * 60)
    if FAIL == 0:
        print(" ALL PART 40 CHECKS PASSED (" + str(PASS) + "/" + str(PASS) + ")")
        return 0
    print(" " + str(FAIL) + " of " + str(PASS + FAIL) + " FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
