# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 132 smoke test - execution tracing."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 132: execution tracing ===")

# 1. File exists + parses
f = SRC / "tracing.py"
check("tracing.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("tracing.py parses", True)
except SyntaxError as e:
    check("tracing.py parses", False, str(e))

# 2. Orchestrator wired
orc = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator has _execute_tool_impl",
      "async def _execute_tool_impl(tool_name" in orc)
check("orchestrator has span wrapper",
      "Part 132: span-wrapped wrapper" in orc)
check("orchestrator has start_trace",
      "_trace_id = _tr132.start_trace(" in orc)
check("orchestrator has finish_trace (happy)",
      'finish_trace(\n                status="ok"' in orc
      or 'finish_trace(status="ok"' in orc)
check("orchestrator has finish_trace (failure)",
      'finish_trace(status="error")' in orc)
check("orchestrator still calls _execute_tool_impl",
      "_res = await _execute_tool_impl(" in orc)

# 3. Routes wired
routes = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("route /api/traces", '@router.get("/api/traces")' in routes)
check("route /api/traces/stats", '@router.get("/api/traces/stats")' in routes)
check("route /api/traces/{id}", '@router.get("/api/traces/{trace_id}")' in routes)
check("route /api/traces/clear", '@router.post("/api/traces/clear")' in routes)

# 4. Functional: tracing module API
sys.path.insert(0, str(SRC.parent))
from sunnyware import tracing as T

T.clear_traces()
check("stats on empty buffer", T.stats()["trace_count"] == 0)

tid = T.start_trace(role="actuary", session_uuid="sess-1",
                    prompt="compute IBNR")
check("start_trace returns hex id", isinstance(tid, str) and len(tid) == 16)
check("current_trace_id == tid", T.current_trace_id() == tid)

span = T.add_span("tool_call", "python_eval",
                  attributes={"tool.name": "python_eval"})
check("add_span returns span dict", isinstance(span, dict) and "span_id" in span)
check("span kind is tool_call", span["kind"] == "tool_call")

T.finish_span(span, status="ok",
              extra={"tool.result_keys": ["result"]})
check("span finished_at set", span["finished_at"] is not None)
check("span duration_ms set", isinstance(span["duration_ms"], int))

T.finish_trace(status="ok", result_summary={"steps_count": 2})
check("finish_trace clears contextvar", T.current_trace_id() is None)

t = T.get_trace(tid)
check("get_trace returns trace", t is not None)
check("trace has parent_trace_id field", "parent_trace_id" in t)
check("trace status is ok", t["status"] == "ok")
check("trace has 1 span", len(t["spans"]) == 1)
check("trace.result_summary captured",
      t.get("result_summary", {}).get("steps_count") == 2)

# 5. Nested delegation via parent_trace_id
T.clear_traces()
parent_tid = T.start_trace(role="cfo", prompt="delegate this")
child_tid = T.start_trace(role="cdo", prompt="sub-task",
                          parent_trace_id=parent_tid)
T.finish_trace(status="ok")
parent = T.get_trace(parent_tid)
child = T.get_trace(child_tid)
check("child trace has parent_trace_id",
      child and child["parent_trace_id"] == parent_tid)
check("parent trace id != child",
      parent_tid != child_tid)

# 6. Ring buffer caps at _MAX_TRACES
T.clear_traces()
max_traces = T._MAX_TRACES
check("_MAX_TRACES == 200", max_traces == 200)
for i in range(max_traces + 5):
    ttid = T.start_trace(role="general", prompt=f"p{i}")
    T.finish_trace(status="ok")
check("buffer capped at _MAX_TRACES",
      T.stats()["trace_count"] == max_traces,
      f"n={T.stats()['trace_count']}")

# 7. get_recent_traces respects limit + role filter
T.clear_traces()
for _ in range(3):
    T.start_trace(role="actuary", prompt="x"); T.finish_trace(status="ok")
T.start_trace(role="cfo", prompt="y"); T.finish_trace(status="ok")
check("get_recent_traces limit",
      len(T.get_recent_traces(limit=2)) == 2)
check("get_recent_traces role filter",
      len(T.get_recent_traces(role="actuary")) == 3)
check("get_recent_traces newest first",
      T.get_recent_traces(limit=1)[0]["role"] == "cfo")

# 8. clear_traces returns count
T.clear_traces()
T.start_trace(role="x", prompt="a"); T.finish_trace()
n = T.clear_traces()
check("clear_traces returns count", n == 1)
check("stats after clear", T.stats()["trace_count"] == 0)

# 9. Files parse
for fp in [SRC / "tracing.py", SRC / "orchestrator.py",
           SRC / "routes" / "meta.py"]:
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
