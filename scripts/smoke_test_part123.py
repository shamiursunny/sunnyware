# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 123 smoke test - interactive Plotly charts in chat."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 123: interactive Plotly charts ===")

# 1. _sandbox.py has capture_plotly
sb = (SRC / "tools" / "_sandbox.py").read_text(encoding="utf-8")
check("_sandbox.py has capture_plotly",
      "def capture_plotly" in sb)
check("capture_plotly uses plotly.io.to_json",
      "from plotly.io import to_json" in sb)
check("capture_plotly caps size",
      "MAX_PLOTLY_BYTES" in sb)

# 2. python_eval wires it
pe = (SRC / "tools" / "python_eval.py").read_text(encoding="utf-8")
check("python_eval calls capture_plotly",
      "pl_cap = _sandbox.capture_plotly(g)" in pe)
check("python_eval still calls capture_chart",
      "chart = _sandbox.capture_chart(g.get(\"plt\"))" in pe)

# 3. orchestrator helper
orc = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator has _inject_plotly_div",
      "def _inject_plotly_div" in orc)
check("orchestrator emits sunnyware-plotly div",
      "sunnyware-plotly" in orc)
check("orchestrator base64-encodes payload",
      "_b64.b64encode" in orc)
check("orchestrator still injects matplotlib",
      "_inject_chart_base64" in orc)

# 4. WebUI wiring
ui = (SRC / "webui.py").read_text(encoding="utf-8")
check("webui loads plotly CDN",
      "cdn.plot.ly/plotly" in ui)
check("webui has _renderPendingPlotly",
      "_renderPendingPlotly" in ui)
check("webui uses Plotly.newPlot",
      "Plotly.newPlot" in ui)
check("webui auto-hooks into renderAgentHtml",
      "raw.indexOf('sunnyware-plotly')" in ui)
check("webui has .sunnyware-plotly CSS",
      ".sunnyware-plotly" in ui)
check("webui keeps marked.parse pipeline",
      "marked.parse(wrapBareBase64(text))" in ui)

# 5. Files parse
for fp in [SRC / "tools" / "_sandbox.py",
           SRC / "tools" / "python_eval.py",
           SRC / "orchestrator.py",
           SRC / "webui.py"]:
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
