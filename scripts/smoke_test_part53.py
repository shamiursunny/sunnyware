#!/usr/bin/env python3
"""Part 53 smoke test — forecast_arima tool."""
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
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def main():
    print("=" * 62)
    print(" Part 53 — forecast_arima tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/forecast_arima.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"
    req_file = ROOT / "requirements.txt"

    check("forecast_arima.py exists", tool_file.exists())
    check("requirements.txt has statsmodels",
          req_file.exists() and "statsmodels" in req_file.read_text(encoding="utf-8"))

    if not tool_file.exists():
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class ForecastArimaTool" in src)
    check("name = forecast_arima", 'name = "forecast_arima"' in src)
    check("auto order grid", "_auto_order" in src)
    check("has periods parameter", '"periods"' in src)
    check("has order parameter", '"order"' in src)
    check("returns forecast array", '"forecast"' in src)
    check("returns AIC", '"aic"' in src)
    check("returns RMSE", '"rmse_in_sample"' in src)
    check("registered in __init__",
          "ForecastArimaTool.name: ForecastArimaTool()" in init_src)

    try:
        ast.parse(src)
        check("forecast_arima.py parses", True)
    except SyntaxError as e:
        check("forecast_arima.py parses", False, detail=str(e))

    try:
        import statsmodels  # noqa
        check("statsmodels importable", True)
    except Exception as e:
        check("statsmodels importable", False, detail=str(e))
        return 1 if FAIL else 0

    # Integration — synthetic trend series
    async def run(**kw):
        from sunnyware.tools.forecast_arima import ForecastArimaTool
        return await ForecastArimaTool().run(kw)

    # Clean linear-ish series
    series = [10 + i * 2 + ((i * 7) % 3) for i in range(30)]

    r1 = asyncio.run(run(data=series, periods=5))
    check("basic forecast succeeds", "error" not in r1,
          detail=str(r1)[:200] if r1.get("error") else "")
    if not r1.get("error"):
        check("returns 5 forecast values",
              len(r1.get("forecast", [])) == 5)
        check("forecast values numeric",
              all(isinstance(x, (int, float)) for x in r1.get("forecast", [])))
        check("order is 3-tuple",
              isinstance(r1.get("order"), list) and len(r1["order"]) == 3)
        check("auto_selected is True", r1.get("auto_selected") is True)
        check("AIC returned as float", isinstance(r1.get("aic"), (int, float)))

    # Explicit order
    r2 = asyncio.run(run(data=series, periods=3, order=[1, 1, 0]))
    check("explicit order accepted", "error" not in r2,
          detail=str(r2)[:120] if r2.get("error") else "")
    if not r2.get("error"):
        check("explicit order applied", r2.get("order") == [1, 1, 0])
        check("auto_selected is False", r2.get("auto_selected") is False)

    # Rejections
    r3 = asyncio.run(run(data=[1, 2]))  # too short
    check("short series rejected", "error" in r3)

    r4 = asyncio.run(run(data=[1, 2, "x", 4]))  # non-numeric
    check("non-numeric rejected", "error" in r4)

    r5 = asyncio.run(run(file="../../etc/passwd", column="x"))
    check("workspace escape rejected", "error" in r5)

    r6 = asyncio.run(run(file="nonexistent.csv", column="x"))
    check("missing file rejected", "error" in r6)

    r7 = asyncio.run(run(data=series, file="x"))  # missing column
    # data takes precedence, so this should succeed — verify
    check("data takes precedence over file",
          "error" not in r7 or "provide either" in str(r7.get("error", "")))

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
