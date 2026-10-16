# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 148 smoke - extended auditor spec sidecar."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 148: extended auditor spec sidecar ===")

spec_p = SRC / "static" / "auditor_prompt_full.txt"
check("static/auditor_prompt_full.txt exists", spec_p.exists())
spec = spec_p.read_text(encoding="utf-8") if spec_p.exists() else ""
check("sidecar has content", len(spec) > 3000, "size=%d" % len(spec))
check("sidecar has CANONICAL TAXONOMY", "CANONICAL TAXONOMY" in spec)
check("sidecar has ROOT CAUSE", "ROOT CAUSE" in spec)
check("sidecar has FULL PIPELINE", "FULL PIPELINE" in spec)
check("sidecar has ANTI-OVERREACH", "ANTI-OVERREACH" in spec)
check("sidecar has no-defect wording",
      "No demonstrated defect; no canonical error label applies." in spec)

tool_p = SRC / "tools" / "auditor_full_spec.py"
check("tools/auditor_full_spec.py exists", tool_p.exists())
tt = tool_p.read_text(encoding="utf-8") if tool_p.exists() else ""
check("tool has class", "class AuditorFullSpecTool" in tt)
check("tool has name = auditor_full_spec",
      'name = "auditor_full_spec"' in tt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as T
from sunnyware import roles as R

check("registered in tool registry",
      "auditor_full_spec" in T.tool_names())
check("total tools >= 81", len(T.tool_names()) >= 81,
      "n=%d" % len(T.tool_names()))

atools = set(R.active_tool_names("auditor") or [])
check("auditor tools == 4", len(atools) == 4, "n=%d" % len(atools))
check("auditor has auditor_full_spec", "auditor_full_spec" in atools)
check("auditor has calculator", "calculator" in atools)
check("auditor has python_eval", "python_eval" in atools)
check("auditor has read_file", "read_file" in atools)

p = R.prompt_addon("auditor") or ""
check("prompt has call-once hint",
      "Call calculator ONCE per unique expression" in p)
# Part 149: prompt now uses "SIDECAR TRIGGERS:" block. Accept either
# the old "call auditor_full_spec ONCE" phrasing or the new block.
check("prompt has sidecar hint",
      "auditor_full_spec ONCE" in p or "SIDECAR TRIGGERS:" in p)

async def _test():
    t = T.get_tool("auditor_full_spec")
    if not t:
        return {"ok": False, "error": "not found"}
    return await t.run({})

r = asyncio.run(_test())
check("tool returns ok", r.get("ok") is True)
check("tool returns spec text", isinstance(r.get("spec"), str))
check("tool spec length matches file",
      r.get("length") == len(spec),
      "returned=%s file=%s" % (r.get("length"), len(spec)))

async def _test_section():
    t = T.get_tool("auditor_full_spec")
    return await t.run({"section": "CANONICAL TAXONOMY"})

r2 = asyncio.run(_test_section())
check("section arg accepted", r2.get("ok") is True)
check("section hint echoed",
      r2.get("section_hint") == "CANONICAL TAXONOMY")

for fp in [SRC / "tools" / "auditor_full_spec.py",
           SRC / "tools" / "__init__.py",
           SRC / "roles.py"]:
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
