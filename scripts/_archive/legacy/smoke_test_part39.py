#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 39 smoke test — JSON export/import for sessions."""

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
    print(" Part 39 smoke test — JSON export/import")
    print("=" * 60)
    print()

    try:
        from sunnyware import webui
    except Exception as e:
        print("[FAIL] cannot import webui: " + type(e).__name__ + ": " + str(e))
        return 1

    html = webui.HTML

    print("Markers present in served HTML:")
    check("exportBtn button",     'id="exportBtn"' in html)
    check("importBtn button",     'id="importBtn"' in html)
    check("importInput file",     'id="importInput"' in html)
    check("exportSessions fn",    "function exportSessions()" in html)
    check("importSessions fn",    "async function importSessions(" in html)
    check("exportBtn wired",      "exportBtn.addEventListener" in html)
    check("importBtn wired",      "importBtn.addEventListener" in html)
    check("import change handler", "importInput.addEventListener('change'" in html)

    print()
    print("Structure markers preserved:")
    check("sidebar intact",       'id="sidebar"' in html)
    check("newChatBtn intact",    'id="newChatBtn"' in html)
    check("sessionList intact",   'id="sessionList"' in html)
    check("chat div intact",      'id="chat"' in html)

    print()
    print("Escaping sanity:")
    bad_patterns = [chr(39) + chr(10) + "     ", chr(39) + chr(10) + "  "]
    present_bad = [p for p in bad_patterns if p in html]
    check("no raw newlines in JS strings", len(present_bad) == 0)

    print()
    print("=" * 60)
    if FAIL == 0:
        print(" ALL PART 39 CHECKS PASSED (" + str(PASS) + "/" + str(PASS) + ")")
        return 0
    print(" " + str(FAIL) + " of " + str(PASS + FAIL) + " FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
