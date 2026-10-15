# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 122 smoke test - workflow registry."""
from pathlib import Path
import ast, asyncio, json, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 122: workflow registry ===")

# 1. File
f = SRC / "tools" / "workflow_registry.py"
check("workflow_registry.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("workflow_registry.py parses", True)
except SyntaxError as e:
    check("workflow_registry.py parses", False, str(e))

# 2. Registration
init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("__init__.py imports WorkflowRegistryTool",
      "from .workflow_registry import WorkflowRegistryTool" in init)
check("__init__.py registers WorkflowRegistryTool",
      "WorkflowRegistryTool.name: WorkflowRegistryTool()" in init)

# 3. Registry
sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("workflow_registry in registry", "workflow_registry" in names)
check("registry size >= 73", len(names) >= 73, f"n={len(names)}")

# 4. API surface
from sunnyware.tools.workflow_registry import WorkflowRegistryTool
inst = WorkflowRegistryTool()
check("name == workflow_registry", inst.name == "workflow_registry")
check("description mentions workflow", "workflow" in inst.description.lower())
check("parameters have action+name+steps+description",
      {"action", "name", "steps", "description"} <= set(inst.parameters))

# 5. Behavior
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"action": "bogus"})
    r3 = await inst.run({"action": "list"})
    r4 = await inst.run({"action": "save", "name": "bad!name",
                         "steps": [{"role": "actuary", "task": "x"}]})
    r5 = await inst.run({"action": "save", "name": "p122_smoke",
                         "steps": [{"role": "actuary", "task": "compute ibnr"},
                                   {"role": "quant", "task": "analyze"}],
                         "description": "smoke test"})
    r6 = await inst.run({"action": "save", "name": "p122_bad_role",
                         "steps": [{"role": "wizard", "task": "x"}]})
    r7 = await inst.run({"action": "save", "name": "p122_no_steps",
                         "steps": []})
    r8 = await inst.run({"action": "get", "name": "p122_smoke"})
    r9 = await inst.run({"action": "delete", "name": "p122_smoke"})
    r10 = await inst.run({"action": "get", "name": "p122_smoke"})
    return r1, r2, r3, r4, r5, r6, r7, r8, r9, r10

r1, r2, r3, r4, r5, r6, r7, r8, r9, r10 = asyncio.run(probe())
check("no action -> error", "error" in r1)
check("unknown action -> error+available",
      "error" in r2 and "available" in r2)
check("list returns workflows array",
      isinstance(r3.get("workflows"), list))
check("invalid name rejected",
      "error" in r4 and "invalid name" in r4["error"])
check("save ok",
      r5.get("saved") is True and r5["workflow"]["step_count"] == 2)
check("unknown role rejected",
      "error" in r6 and "unknown role" in r6["error"])
check("empty steps rejected",
      "error" in r7 and "non-empty" in r7["error"])
check("get returns steps",
      isinstance(r8.get("steps"), list) and len(r8["steps"]) == 2)
check("get returns role canonical",
      r8["steps"][0]["role"] == "actuary")
check("delete ok", r9.get("deleted") is True)
check("get after delete not found",
      "error" in r10 and "not found" in r10["error"])

# 6. Files parse
for fp in [SRC / "tools" / "workflow_registry.py",
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
