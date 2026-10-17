# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 170 smoke - session title persistence."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 170: session title persistence ===")

sp = SRC / "sessions.py"
st = sp.read_text(encoding="utf-8")
check("sessions.py: set_title defined",
      "async def set_title(" in st)
check("sessions.py: get_title defined",
      "async def get_title(" in st)
check("sessions.py: merges into metadata",
      "jsonb_build_object('title'" in st)
check("sessions.py: reads metadata->>'title'",
      "metadata->>'title'" in st)
check("sessions.py: caps at 200 chars",
      "[:200]" in st)

rt = (SRC / "routes" / "sessions.py").read_text(encoding="utf-8")
check("routes: GET /title route",
      '@router.get("/api/sessions/{session_key}/title")' in rt)
check("routes: PUT /title route",
      '@router.put("/api/sessions/{session_key}/title")' in rt)
check("routes: title_put calls set_title",
      "await sessions_store.set_title(" in rt)
check("routes: title_put validates non-empty",
      'if not title:' in rt)
check("routes: title_put returns persisted flag",
      '"persisted": ok' in rt)

wt = (SRC / "webui.py").read_text(encoding="utf-8")
check("webui: renameSession PUTs to backend",
      "Part 170: persist to backend" in wt)
check("webui: hydrateFromNeon prefers metadata.title",
      "Part 170: prefer custom title" in wt)
check("webui: fires PUT /title from rename",
      "/title'," in wt)

for fp in [sp, SRC / "routes" / "sessions.py", SRC / "webui.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print("")
print(f"{passed}/{total} checks passed")
if passed < total:
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
