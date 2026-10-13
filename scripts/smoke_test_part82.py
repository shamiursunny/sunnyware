#!/usr/bin/env python3
"""Part 82 smoke test - metrics_batch."""
import ast, sys, asyncio
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
        PASS += 1; print("  [PASS] " + label)
    else:
        FAIL += 1; print("  [FAIL] " + label + (" - " + detail if detail else ""))


def main():
    print("=" * 62)
    print(" Part 82 - metrics_batch (empyrical)")
    print("=" * 62)

    f = ROOT / "src/sunnyware/tools/metrics_batch.py"
    check("metrics_batch.py exists", f.exists())
    req = ROOT / "requirements.txt"
    check("empyrical in requirements",
          req.exists() and "empyrical" in req.read_text(encoding="utf-8"))
    if not f.exists(): return 1

    src = f.read_text(encoding="utf-8")
    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")

    check("class defined", "class MetricsBatchTool" in src)
    check("name = metrics_batch", 'name = "metrics_batch"' in src)
    check("numpy fallback", "_numpy_metrics" in src)
    check("empyrical path", "_empyrical_metrics" in src)
    check("summary block", "best_sharpe" in src)
    check("registered", "MetricsBatchTool.name: MetricsBatchTool()" in init_src)

    try:
        ast.parse(src); check("parses", True)
    except SyntaxError as e:
        check("parses", False, detail=str(e))

    # Check empyrical import status
    try:
        import empyrical  # noqa
        check("empyrical importable locally", True)
    except Exception as e:
        print("  [SKIP] empyrical not installed locally: " + str(e)[:60])
        print("  (this is fine - code falls back to numpy)")

    # Integration
    async def run(**kw):
        from sunnyware.tools.metrics_batch import MetricsBatchTool
        return await MetricsBatchTool().run(kw)

    s1 = [0.01, -0.005, 0.012, -0.002, 0.008, -0.001, 0.015, -0.004, 0.009, 0.002]
    s2 = [-0.02, -0.01, -0.015, 0.005, -0.008, 0.001, -0.012, -0.003, -0.009, -0.005]
    s3 = [0.001, 0.0005, -0.0002, 0.0008, 0.0003, -0.0001, 0.0006, 0.0002, 0.0004, 0.0009]

    r = asyncio.run(run(series=[
        {"name": "fund_A", "returns": s1},
        {"name": "fund_B", "returns": s2},
        {"name": "bond_fund", "returns": s3},
    ]))
    check("call succeeds", "error" not in r,
          detail=str(r)[:200] if r.get("error") else "")
    if "error" not in r:
        check("3 series processed", r.get("series_count") == 3)
        check("all 3 ok", r.get("ok_count") == 3, detail=str(r.get("ok_count")))
        results = r.get("results", [])
        check("fund_A has sharpe", results[0].get("sharpe_ratio") is not None)
        check("fund_A has max_drawdown", "max_drawdown" in results[0])
        check("fund_A has var_95", "var_95" in results[0])
        check("summary has best_sharpe", "best_sharpe" in r.get("summary", {}))
        check("summary has worst_drawdown", "worst_drawdown" in r.get("summary", {}))
        # Best sharpe exists and is one of our series
        bs = r.get("summary", {}).get("best_sharpe")
        check("best_sharpe is one of the input series",
              bs and bs.get("name") in ("fund_A", "fund_B", "bond_fund"),
              detail=str(bs))

    # Rejections
    check("empty series rejected",
          "error" in asyncio.run(run(series=[])))
    check("no args rejected", "error" in asyncio.run(run()))
    check("too many series rejected",
          "error" in asyncio.run(run(series=[{"name": "x", "returns": [0.1, 0.2]}] * 30)))
    bad = asyncio.run(run(series=[{"name": "x", "returns": ["a", "b"]}]))
    # Per-series error is expected (not top-level)
    entries = bad.get("results", [])
    check("bad returns produces per-series error",
          entries and "error" in entries[0],
          detail=str(entries)[:200])

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
