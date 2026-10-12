#!/usr/bin/env python3
"""Part 55 smoke test — financial_metrics tool."""
import ast, sys, asyncio, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

PASS, FAIL = 0, 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def main():
    print("=" * 62)
    print(" Part 55 — financial_metrics tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/financial_metrics.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("financial_metrics.py exists", tool_file.exists())
    if not tool_file.exists():
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class FinancialMetricsTool" in src)
    check("name = financial_metrics", 'name = "financial_metrics"' in src)
    check("supports returns", '"returns"' in src)
    check("supports prices", '"prices"' in src)
    check("supports file+column", '"file"' in src and '"column"' in src)
    check("Sharpe computed", "sharpe_ratio" in src)
    check("Sortino computed", "sortino_ratio" in src)
    check("Max drawdown computed", "max_drawdown" in src)
    check("VaR/CVaR computed", "var_95_historical" in src and "cvar_95_historical" in src)
    check("annualization supported", "periods_per_year" in src)
    check("registered in __init__",
          "FinancialMetricsTool.name: FinancialMetricsTool()" in init_src)

    try:
        ast.parse(src)
        check("financial_metrics.py parses", True)
    except SyntaxError as e:
        check("financial_metrics.py parses", False, detail=str(e))

    # Integration tests — synthetic series with known-ish properties
    async def run(**kw):
        from sunnyware.tools.financial_metrics import FinancialMetricsTool
        return await FinancialMetricsTool().run(kw)

    # Small positive-drift return series (daily)
    # 60 returns averaging ~0.0008/day, low vol -> positive Sharpe
    import random
    random.seed(42)
    rets = [0.0008 + random.uniform(-0.01, 0.01) for _ in range(60)]

    r = asyncio.run(run(returns=rets, periods_per_year=252))
    check("basic call succeeds", "error" not in r,
          detail=str(r)[:200] if r.get("error") else "")
    if "error" not in r:
        check("has sharpe_ratio",
              isinstance(r.get("risk_adjusted", {}).get("sharpe_ratio"), (int, float)))
        check("has sortino_ratio",
              isinstance(r.get("risk_adjusted", {}).get("sortino_ratio"), (int, float, type(None))))
        check("has max_drawdown",
              isinstance(r.get("drawdown", {}).get("max_drawdown"), (int, float)))
        check("max_drawdown <= 0", r["drawdown"]["max_drawdown"] <= 0)
        check("has var_95",
              isinstance(r.get("tail_risk", {}).get("var_95_historical"), (int, float)))
        check("VaR is <= 0", r["tail_risk"]["var_95_historical"] <= 0)
        check("has annualized_return",
              isinstance(r.get("returns_summary", {}).get("annualized_return"), (int, float)))
        check("has annualized_volatility",
              isinstance(r.get("returns_summary", {}).get("annualized_volatility"), (int, float)))

    # Prices mode — should convert to returns and work identically
    prices = [100.0]
    for x in rets:
        prices.append(prices[-1] * (1 + x))
    r2 = asyncio.run(run(prices=prices))
    check("prices mode succeeds", "error" not in r2,
          detail=str(r2)[:200] if r2.get("error") else "")
    if "error" not in r2:
        check("prices mode n_periods < len(prices)",
              r2["n_periods"] == len(prices) - 1)

    # All-positive returns -> Sortino should be None (undefined)
    r3 = asyncio.run(run(returns=[0.01] * 30))
    check("all-positive returns -> Sortino None",
          r3.get("risk_adjusted", {}).get("sortino_ratio") is None)

    # Rejections
    r4 = asyncio.run(run(returns=[0.01]))  # too short
    check("too-short rejected", "error" in r4)

    r5 = asyncio.run(run(returns=[0.01, "x", 0.02]))
    check("non-numeric rejected", "error" in r5)

    r6 = asyncio.run(run())
    check("no args rejected", "error" in r6)

    r7 = asyncio.run(run(file="../../etc/passwd", column="x"))
    check("workspace escape rejected", "error" in r7)

    r8 = asyncio.run(run(file="nonexistent.csv", column="x"))
    check("missing file rejected", "error" in r8)

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
