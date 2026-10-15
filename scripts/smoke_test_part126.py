# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 126 smoke test - persistent document library."""
from pathlib import Path
import ast, asyncio, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 126: persistent document library ===")

f = SRC / "tools" / "document_library.py"
check("document_library.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("document_library.py parses", True)
except SyntaxError as e:
    check("document_library.py parses", False, str(e))

init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("__init__ imports DocumentLibraryTool",
      "from .document_library import DocumentLibraryTool" in init)
check("__init__ registers DocumentLibraryTool",
      "DocumentLibraryTool.name: DocumentLibraryTool()" in init)

sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("document_library in registry", "document_library" in names)
check("registry size >= 76", len(names) >= 76, f"n={len(names)}")

from sunnyware.tools.document_library import (
    DocumentLibraryTool, save_document, get_document, delete_document,
    search_documents, list_documents, stats,
)
inst = DocumentLibraryTool()
check("name == document_library", inst.name == "document_library")
check("description mentions persistent",
      "persistent" in inst.description.lower())
check("parameters include action+name+content+tags+query",
      {"action", "name", "content", "tags", "query"} <= set(inst.parameters))

# Round-trip via tool
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"action": "bogus"})
    r3 = await inst.run({"action": "add", "name": "bad!name", "content": "x"})
    r4 = await inst.run({"action": "add", "name": "p126_doc",
                         "content": "Part 126 content about insurance premiums.",
                         "description": "test doc",
                         "tags": "insurance,client"})
    r5 = await inst.run({"action": "get", "name": "p126_doc"})
    r6 = await inst.run({"action": "search", "query": "premiums"})
    r7 = await inst.run({"action": "search", "query": "insurance"})
    r8 = await inst.run({"action": "list"})
    r9 = await inst.run({"action": "stats"})
    r10 = await inst.run({"action": "delete", "name": "p126_doc"})
    r11 = await inst.run({"action": "get", "name": "p126_doc"})
    return r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11

r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11 = asyncio.run(probe())
check("no action -> error", "error" in r1 and "available" in r1)
check("unknown action -> error", "error" in r2 and "available" in r2)
check("invalid name rejected",
      "error" in r3 and "invalid name" in r3["error"])
check("add ok", r4.get("saved") is True)
check("add returns metadata",
      (r4.get("document") or {}).get("name") == "p126_doc")
check("add captures tags",
      "insurance" in ((r4.get("document") or {}).get("tags") or []))
check("get returns content",
      "premiums" in (r5.get("content") or ""))
check("search by content word",
      r6.get("count", 0) >= 1)
check("search by tag",
      r7.get("count", 0) >= 1)
check("list returns array", isinstance(r8.get("documents"), list))
check("stats has count", "count" in r9)
check("delete ok", r10.get("deleted") is True)
check("get after delete -> not found",
      "error" in r11 and "not found" in r11["error"])

# Roles
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py mentions document_library", '"document_library"' in rt)

from sunnyware import roles as _roles
for role in ("actuary", "cfo"):
    subset = _roles.active_tool_names(role) or []
    check(f"document_library in {role} subset",
          "document_library" in subset)

# Files parse
for fp in [SRC / "tools" / "document_library.py",
           SRC / "tools" / "__init__.py",
           SRC / "roles.py"]:
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
