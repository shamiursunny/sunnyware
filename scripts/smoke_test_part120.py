# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 120 smoke test - script registry + save_as on python_eval."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 120: script registry + save_as ===")

# 1. File exists + parses
f = SRC / "tools" / "script_registry.py"
check("script_registry.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("script_registry.py parses", True)
except SyntaxError as e:
    check("script_registry.py parses", False, str(e))

# 2. Registration
init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("tools/__init__.py imports ScriptRegistryTool",
      "from .script_registry import ScriptRegistryTool" in init)
check("tools/__init__.py registers ScriptRegistryTool",
      "ScriptRegistryTool.name: ScriptRegistryTool()" in init)

# 3. Registry
sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("script_registry in registry", "script_registry" in names)
check("registry size >= 72", len(names) >= 72, f"n={len(names)}")

# 4. python_eval surface extended
pe = (SRC / "tools" / "python_eval.py").read_text(encoding="utf-8")
check("python_eval has save_as param", '"save_as"' in pe)
check("python_eval has description param", '"description"' in pe)
check("python_eval wires save_script_internal",
      "from .script_registry import save_script_internal" in pe)
check("python_eval adds _saved_as on success", '"_saved_as"' in pe)

# 5. ScriptRegistryTool API surface
from sunnyware.tools.script_registry import ScriptRegistryTool
inst = ScriptRegistryTool()
check("name == script_registry", inst.name == "script_registry")
check("description mentions reusable/reuse",
      "reusable" in inst.description.lower() or "reuse" in inst.description.lower())
check("parameters have action+name+code+description",
      {"action", "name", "code", "description"} <= set(inst.parameters))

# 6. Behavior tests (no network)
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"action": "bogus"})
    r3 = await inst.run({"action": "list"})
    r4 = await inst.run({"action": "save", "name": "bad name!", "code": "x=1"})
    r5 = await inst.run({"action": "save", "name": "p120_smoke",
                         "code": "result = 42",
                         "description": "smoke test"})
    r6 = await inst.run({"action": "get", "name": "p120_smoke"})
    r7 = await inst.run({"action": "run", "name": "p120_smoke"})
    r8 = await inst.run({"action": "delete", "name": "p120_smoke"})
    r9 = await inst.run({"action": "get", "name": "p120_smoke"})
    return r1, r2, r3, r4, r5, r6, r7, r8, r9

r1, r2, r3, r4, r5, r6, r7, r8, r9 = asyncio.run(probe())
check("no action -> error", "error" in r1)
check("unknown action -> error+available",
      "error" in r2 and "available" in r2)
check("list -> returns scripts array",
      isinstance(r3.get("scripts"), list))
check("invalid name rejected",
      "error" in r4 and "invalid name" in r4["error"])
check("save ok", r5.get("saved") is True)
check("get returns code", r6.get("code") == "result = 42")
# exec_code returns {'ok':True, 'result':'42', ...}; result is serialized
check("run returns inner result (string-serialized)",
      r7.get("result", {}).get("result") == "42"
      or r7.get("result", {}).get("result") == 42)
check("run returns ok=True",
      r7.get("result", {}).get("ok") is True)
check("delete ok", r8.get("deleted") is True)
check("get after delete -> not found",
      "error" in r9 and "not found" in r9["error"])

# 7. Files parse
for fp in [SRC / "tools" / "script_registry.py",
           SRC / "tools" / "python_eval.py",
           SRC / "tools" / "__init__.py"]:
    try:
        ast.parse(fp.read_text(encoding="utf-8"))
        check(f"{fp.name} parses", True)
    except SyntaxError as e:
        check(f"{fp.name} parses", False, str(e))

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
