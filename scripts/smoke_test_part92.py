# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 92 smoke test - professional HTML /about page."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 92: professional /about HTML page ===")

# 1. HTML file exists
html_path = SRC / "static" / "about.html"
check("static/about.html exists", html_path.is_file())
html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""

# 2. Contains all placeholders
for ph in ["%%VERSION%%", "%%AUTHOR%%", "%%EMAIL%%", "%%PHONE%%",
           "%%WEBSITE%%", "%%GITHUB%%", "%%COPYRIGHT%%", "%%LICENSE%%"]:
    check(f"placeholder {ph}", ph in html)

# 3. Responsive + dark theme markers
check("has viewport meta", 'name="viewport"' in html)
check("has color-scheme dark", 'name="color-scheme" content="dark"' in html)
check("has responsive media query", "@media (max-width: 640px)" in html)
check("uses accent #4ade80", "#4ade80" in html)
check("has 'Back to chat' link", 'href="/ui"' in html and "Back to chat" in html)
check("has grid layout", "display: grid" in html)

# 4. meta.py uses HTMLResponse
meta_src = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("meta.py uses response_class=HTMLResponse on /about",
      'response_class=HTMLResponse' in meta_src and '@router.get("/about"' in meta_src)
check("meta.py reads about.html", "about.html" in meta_src)
check("meta.py loops placeholders", "for k, v in replacements.items()" in meta_src)

# 5. No raw JSON about()
check("old JSON about() removed",
      '"project": "sunnyware",\n        "version": meta.PROJECT_VERSION' not in meta_src)

# Summary
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
