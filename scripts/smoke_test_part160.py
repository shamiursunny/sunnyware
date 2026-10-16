# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 160 smoke - tool-level circuit breakers."""
from pathlib import Path
import ast, os, sys, time

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 160: tool circuit breakers ===")

cbp = SRC / "circuit_breaker.py"
check("circuit_breaker.py exists", cbp.exists())
cbt = cbp.read_text(encoding="utf-8") if cbp.exists() else ""
check("has check()", "def check(" in cbt)
check("has record()", "def record(" in cbt)
check("has is_open()", "def is_open(" in cbt)
check("has snapshot()", "def snapshot(" in cbt)
check("has reset()", "def reset(" in cbt)

ot = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator imports circuit_breaker",
      "from . import circuit_breaker as _cb" in ot)
check("orchestrator has _execute_tool_raw",
      "async def _execute_tool_raw(" in ot)
check("orchestrator has _execute_tool wrapper",
      "async def _execute_tool(" in ot)
check("wrapper returns circuit_open",
      '"error": "circuit_open"' in ot)

mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("GET /api/tools/circuits",
      '"/api/tools/circuits"' in mt)
check("POST /api/tools/circuits/reset",
      '"/api/tools/circuits/reset"' in mt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import circuit_breaker as CB

os.environ["SUNNYWARE_TOOL_BREAKER_ENABLED"] = "1"
os.environ["SUNNYWARE_TOOL_BREAKER_FAILS"] = "3"
os.environ["SUNNYWARE_TOOL_BREAKER_COOLDOWN_S"] = "2"
CB.reset()

check("enabled", CB.enabled() is True)
check("fails threshold 3", CB.fails_threshold() == 3)
check("cooldown 2s", CB.cooldown_seconds() == 2)

d = CB.check("t1")
check("initial allow", d["allow"] is True)

CB.record("t1", False, "boom")
check("after 1 fail still allow", CB.check("t1")["allow"] is True)

CB.record("t1", False, "boom")
check("after 2 fails still allow", CB.check("t1")["allow"] is True)

CB.record("t1", False, "boom")
d = CB.check("t1")
check("after 3 fails -> OPEN", d["allow"] is False)
check("reason circuit_open", d.get("reason") == "circuit_open")
check("has retry_after", isinstance(d.get("retry_after"), int) and
      d["retry_after"] > 0)

snap = CB.snapshot()
tool1 = next((t for t in snap["tools"] if t["name"] == "t1"), None)
check("snapshot shows t1 open", tool1 and tool1["open"] is True)
check("snapshot total_fails=3", tool1 and tool1["total_fails"] == 3)

CB.record("t1", True)
check("after success -> closed", CB.check("t1")["allow"] is True)
snap2 = CB.snapshot()
t1b = next((t for t in snap2["tools"] if t["name"] == "t1"), None)
check("consecutive_fails reset to 0",
      t1b and t1b["consecutive_fails"] == 0)

CB.reset()
CB.record("t2", False, "x")
CB.record("t2", False, "x")
CB.record("t2", False, "x")
check("t2 open", CB.is_open("t2") is True)
time.sleep(2.5)
check("t2 auto-closed after 2.5s", CB.is_open("t2") is False)

CB.reset()
CB.record("t3", False, "x")
CB.record("t4", False, "x")
CB.record("t4", False, "x")
CB.record("t4", False, "x")
check("t3 not open", CB.is_open("t3") is False)
check("t4 open", CB.is_open("t4") is True)

n = CB.reset("t4")
check("reset t4 -> 1", n == 1)
check("t4 closed after reset", CB.is_open("t4") is False)

os.environ["SUNNYWARE_TOOL_BREAKER_ENABLED"] = "0"
CB.reset()
CB.record("t5", False, "x")
CB.record("t5", False, "x")
CB.record("t5", False, "x")
check("disabled -> never opens", CB.is_open("t5") is False)
check("disabled -> check allow", CB.check("t5")["allow"] is True)
os.environ["SUNNYWARE_TOOL_BREAKER_ENABLED"] = "1"

for fp in [cbp, SRC / "orchestrator.py", SRC / "routes" / "meta.py"]:
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
