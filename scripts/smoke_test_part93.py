# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 93 smoke test - professional header redesign."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
WUI = ROOT / "src" / "sunnyware" / "webui.py"

checks = []
def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 93: professional header redesign ===")

src = WUI.read_text(encoding="utf-8")

# 1. New markup
check("brand-mark class present", 'class="brand-mark"' in src)
check("brand-name class present", 'class="brand-name"' in src)
check("session-pill class present", 'class="session-pill"' in src)
check("session-dot class present", 'class="session-dot"' in src)
check("provider-pill class present", 'class="provider-pill"' in src)
check("pill-badge class present", 'class="pill-badge"' in src)
check("icon-btn class present", 'class="icon-btn"' in src)
check("overflow-wrap present", 'class="overflow-wrap"' in src)
check("overflow-item present", 'class="overflow-item"' in src)

# 2. New CSS rules
check("brand-mark CSS defined", ".brand-mark {" in src)
check("session-pill CSS defined", ".session-pill {" in src)
check("icon-btn CSS defined", ".icon-btn {" in src)
check("pill-badge CSS defined", ".pill-badge {" in src)
check("provider-pill CSS defined", ".provider-pill {" in src)
check("pill-badge :empty hidden", ".pill-badge:empty { display: none; }" in src)
check("provider-pill :empty hidden", ".provider-pill:empty" in src)
check("overflow panel .open rule", ".overflow-panel.open {" in src)
check("menuIn animation", "@keyframes menuIn" in src)

# 3. JS: session prefix removed
check("session prefix removed from JS",
      "sidEl.textContent = 'session: '" not in src
      and "sidEl.textContent = getSession()" in src)

# 4. Kept existing IDs (backward-compat with handlers)
for eid in ['id="sid"', 'id="upload"', 'id="docCount"',
            'id="providerBadge"', 'id="overflowPanel"', 'id="overflowMenuBtn"',
            'id="uploadMobile"', 'id="clearMobile"', 'id="docCountMobile"',
            'id="providerBadgeMobile"', 'id="sidMobile"']:
    check(f"preserved {eid}", eid in src)

# 5. Old header-meta-desktop markup gone
check("old header-meta-desktop markup removed",
      '<div class="header-meta-desktop">' not in src)

# 6. Responsive breakpoints present
check("760px breakpoint (hide brand name)", "@media (max-width: 760px)" in src)
check("480px breakpoint (hide session pill)", "@media (max-width: 480px)" in src)

# 6b. Part 93b: paperclip moved into composer
check("composer-input wrapper present", 'class="composer-input"' in src)
check("attach-btn class present", 'class="attach-btn"' in src)
check("attach-btn CSS defined", ".attach-btn {" in src)
check("composer-input CSS defined", ".composer-input {" in src)
check("input has left-padding for paperclip", "padding-left: 46px" in src)
# id="upload" appears exactly once (in composer, not header)
check("id='upload' appears exactly once", src.count('id="upload"') == 1)

# 6c. Part 94: overflow button visible + doc badge as number only
# (base CSS for #overflowMenuBtn must NOT be display: none without .show)
import re as _re
_hidden_default = _re.search(
    r"#overflowMenuBtn\s*\{\s*display:\s*none", src
)
check("overflowMenuBtn NOT hidden by default",
      _hidden_default is None)
check("doc count JS writes number not 'docs:' text",
      "docCountEl.textContent = 'docs: '" not in src
      and "String(_n)" in src)
check("attach-badge CSS tightened (15px)",
      "min-width: 15px; height: 15px" in src and ".attach-btn .pill-badge" in src)

# 6d. Part 95: sidebar footer + upward menu
check("sidebar-footer wrapper present", 'class="sidebar-footer"' in src)
check("sidebar-menu-btn present", 'class="sidebar-menu-btn"' in src)
check("sidebar-menu-label present", 'class="sidebar-menu-label"' in src)
check("sidebar-footer CSS defined", ".sidebar-footer {" in src)
check("sidebar-menu-btn CSS defined", ".sidebar-menu-btn {" in src)
check("menu opens upward (menuInUp)", "@keyframes menuInUp" in src)
check("header no longer has id='clear' button", 'id="clear"' not in src)
check("clearMobile redirects to newChatBtn", "getElementById('newChatBtn')" in src)
check("sidebar-overflow-panel positioned above", ".sidebar-footer .overflow-panel" in src)

# 7. Parses
import ast
try:
    ast.parse(src)
    check("webui.py parses", True)
except SyntaxError as e:
    check("webui.py parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    print("\nFAILED CHECKS:")
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
