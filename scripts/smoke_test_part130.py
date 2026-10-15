# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 130 smoke test - risk_metrics tool."""
from pathlib import Path
import ast, asyncio, json, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 130: risk_metrics tool ===")

f = SRC / "tools" / "risk_metrics.py"
check("risk_metrics.py exists", f.exists())
try:
    ast.parse(f.read_text(encoding="utf-8"))
    check("risk_metrics.py parses", True)
except SyntaxError as e:
    check("risk_metrics.py parses", False, str(e))

init = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
check("__init__ imports RiskMetricsTool",
      "from .risk_metrics import RiskMetricsTool" in init)
check("__init__ registers RiskMetricsTool",
      "RiskMetricsTool.name: RiskMetricsTool()" in init)

sys.path.insert(0, str(SRC.parent))
from sunnyware import tools as tools_registry
names = tools_registry.tool_names()
check("risk_metrics in registry", "risk_metrics" in names)
check("registry size >= 79", len(names) >= 79, f"n={len(names)}")

from sunnyware.tools.risk_metrics import (
    RiskMetricsTool, var_historical, var_parametric, cvar_historical,
    sharpe_ratio, sortino_ratio, max_drawdown, stress_test, beta_metric,
    correlation_matrix, returns_from_prices,
)
inst = RiskMetricsTool()
check("name == risk_metrics", inst.name == "risk_metrics")
check("description mentions VaR", "VaR" in inst.description)
check("description mentions Sharpe", "Sharpe" in inst.description)
check("parameters include action+returns+confidence",
      {"action", "returns", "confidence"} <= set(inst.parameters))

# Synthetic returns
R = [0.01, -0.02, 0.03, -0.01, 0.005, -0.015, 0.02, -0.005,
     0.008, -0.03, 0.015, 0.004, -0.012, 0.022, -0.018,
     0.006, -0.008, 0.011, 0.003, -0.025]

# VaR historical
vh = var_historical(R, 0.95)
check("var_historical has methodology",
      vh.get("methodology") == "historical simulation")
check("var_historical loss > 0", vh["var_loss"] > 0, str(vh["var_loss"]))
check("var_historical var_return < 0",
      vh["var_return"] < 0, str(vh["var_return"]))

# VaR parametric
vp = var_parametric(R, 0.95)
check("var_parametric has z_score", "z_score" in vp)
check("var_parametric z_score is negative",
      vp["z_score"] < 0, str(vp["z_score"]))
check("var_parametric loss > 0", vp["var_loss"] > 0)

# CVaR should be more negative than VaR
c = cvar_historical(R, 0.95)
check("cvar_loss > var_historical loss (fatter tail)",
      c["cvar_loss"] >= vh["var_loss"] - 1e-9,
      f"cvar={c['cvar_loss']:.4f} var={vh['var_loss']:.4f}")
check("cvar tail_observations >= 1", c["tail_observations"] >= 1)

# Sharpe / Sortino
s = sharpe_ratio(R)
check("sharpe is finite", s.get("sharpe") is not None and isinstance(s["sharpe"], float))
so = sortino_ratio(R)
check("sortino is finite", so.get("sortino") is not None)
# When mean return is negative, both ratios are negative. Sortino has
# smaller denominator (downside dev < std), so |sortino| >= |sharpe|
# in magnitude. Compare magnitudes to be sign-agnostic.
check("|sortino| >= |sharpe| (downside dev <= total std)",
      abs(so["sortino"]) >= abs(s["sharpe"]) - 1e-9,
      f"s={s['sharpe']:.3f} so={so['sortino']:.3f}")

# Max drawdown
md = max_drawdown(R)
check("max_drawdown is negative or zero", md["max_drawdown"] <= 0)
check("max_drawdown_pct matches", abs(md["max_drawdown"]) * 100 == md["max_drawdown_pct"])
check("max_drawdown has peak+trough indices",
      isinstance(md["peak_index"], int) and isinstance(md["trough_index"], int))

# Returns from prices
r_from_p = returns_from_prices([100, 101, 100, 102])
check("returns_from_prices length n-1", len(r_from_p) == 3)
check("returns_from_prices correct first",
      abs(r_from_p[0] - 0.01) < 1e-9, str(r_from_p[0]))

# Stress test
st = stress_test(R, [-0.05, -0.10, -0.20])
check("stress_test base_var_95 present", "base_var_95" in st)
check("stress_test returns 3 scenarios", len(st["scenarios"]) == 3)
check("stress_test shock -0.20 has stressed_var",
      st["scenarios"][2]["stressed_var_95"] > 0)

# Correlation
cm = correlation_matrix({"a": R, "b": R})
check("correlation of self with self == 1.0",
      abs(cm["matrix"][0][1] - 1.0) < 1e-9)

# Beta
b = beta_metric(R, R)
check("beta of self vs self == 1.0", abs(b["beta"] - 1.0) < 1e-9)

# Behavior via tool
async def probe():
    r1 = await inst.run({})
    r2 = await inst.run({"action": "bogus"})
    r3 = await inst.run({"action": "summary"})
    r4 = await inst.run({"action": "summary", "returns": json.dumps(R)})
    r5 = await inst.run({"action": "var", "returns": json.dumps(R), "confidence": 0.99})
    r6 = await inst.run({"action": "from_prices", "prices": "[100,101,102,101.5]"})
    r7 = await inst.run({"action": "summary", "returns": "not json"})
    r8 = await inst.run({"action": "stress_test", "returns": json.dumps(R), "shocks": "[-0.1]"})
    r9 = await inst.run({"action": "beta", "returns": json.dumps(R), "benchmark_returns": json.dumps(R)})
    r10 = await inst.run({"action": "correlation", "series": '{"x": ' + json.dumps(R) + ', "y": ' + json.dumps(R) + '}'})
    return r1, r2, r3, r4, r5, r6, r7, r8, r9, r10

t1, t2, t3, t4, t5, t6, t7, t8, t9, t10 = asyncio.run(probe())
check("no action -> error + available", "error" in t1 and "available" in t1)
check("unknown action -> error + available", "error" in t2 and "available" in t2)
check("summary without returns -> error", "error" in t3)
check("summary with returns -> dict with var_historical_95",
      "var_historical_95" in t4)
check("var action confidence 0.99 works",
      "historical" in t5 and t5["historical"].get("var_loss") is not None)
check("from_prices returns array", isinstance(t6.get("returns"), list))
check("invalid JSON returns -> error",
      "error" in t7 and "not valid JSON" in t7["error"])
check("stress_test returns scenarios", isinstance(t8.get("scenarios"), list))
check("beta action returns beta ~ 1.0",
      abs((t9.get("beta") or 0) - 1.0) < 1e-6)
check("correlation returns matrix",
      isinstance(t10.get("matrix"), list))

# Role wiring
rt = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py mentions risk_metrics", '"risk_metrics"' in rt)

from sunnyware import roles as _roles
for role in ("risk_ins", "quant"):
    subset = _roles.active_tool_names(role) or []
    check(f"risk_metrics in {role} subset",
          "risk_metrics" in subset)

# Files parse
for fp in [SRC / "tools" / "risk_metrics.py",
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
