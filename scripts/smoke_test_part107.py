# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 107-109 smoke test - financial data tools for FP&A/quant."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 107-109: financial data tools ===")

# 1. Shared helper
hp = SRC / "tools" / "_financial_http.py"
check("_financial_http.py exists", hp.is_file())
helper = hp.read_text(encoding="utf-8") if hp.is_file() else ""
try:
    ast.parse(helper)
    check("_financial_http.py parses", True)
except SyntaxError as e:
    check("_financial_http.py parses", False, str(e))
for fn in ["def get_json(", "def env_required(", "def cache_get(", "def cache_set("]:
    check(f"{fn} present", fn in helper)

# 2. Tool files
tools = [
    ("edgar_fundamentals.py", "EdgarFundamentalsTool", "edgar_fundamentals"),
    ("fred_economic.py", "FredEconomicTool", "fred_economic"),
    ("finnhub_quote.py", "FinnhubTool", "finnhub_quote"),
    ("tiingo_prices.py", "TiingoPricesTool", "tiingo_prices"),
    ("marketaux_news.py", "MarketauxNewsTool", "marketaux_news"),
    ("twelvedata_prices.py", "TwelveDataTool", "twelvedata_prices"),
    ("fmp_fundamentals.py", "FmpFundamentalsTool", "fmp_fundamentals"),
]
for fname, cls, tname in tools:
    fp = SRC / "tools" / fname
    check(f"{fname} exists", fp.is_file())
    src = fp.read_text(encoding="utf-8") if fp.is_file() else ""
    try:
        ast.parse(src)
        check(f"{fname} parses", True)
    except SyntaxError as e:
        check(f"{fname} parses", False, str(e))
    check(f"{cls} defined", f"class {cls}" in src)
    check(f'name = "{tname}"', f'name = "{tname}"' in src)
    check(f"{fname} has async run", "async def run(" in src)

# 3. Registry
init_src = (SRC / "tools" / "__init__.py").read_text(encoding="utf-8")
for fname, cls, tname in tools:
    check(f"registered: {tname}", f"{cls}.name: {cls}()" in init_src)
    check(f"imported: {cls}", f"from .{fname[:-3]} import {cls}" in init_src)

# 4. .env.example documents keys
env_ex = ROOT / ".env.example"
if env_ex.exists():
    et = env_ex.read_text(encoding="utf-8")
    for key in ["FRED_API_KEY", "FINNHUB_API_KEY", "TIINGO_API_KEY",
                "MARKETAUX_API_KEY", "TWELVEDATA_API_KEY", "FMP_API_KEY",
                "SEC_USER_AGENT"]:
        check(f".env.example documents {key}", f"{key}=" in et)

# 5. Live import
sys.path.insert(0, str(SRC.parent))
try:
    from sunnyware import tools as tr
    names = tr.tool_names()
    for _, _, tname in tools:
        check(f"live: {tname} in tool_names()", tname in names)
    check("tool count >= 66", len(names) >= 66, f"{len(names)} tools")
except Exception as e:
    check("live import works", False, f"{type(e).__name__}: {e}")

# 6. EDGAR works without key (static check on the tool's behavior path)
edgar_src = (SRC / "tools" / "edgar_fundamentals.py").read_text(encoding="utf-8")
check("edgar uses SEC_USER_AGENT env", "SEC_USER_AGENT" in edgar_src)
check("edgar hits data.sec.gov", "data.sec.gov" in edgar_src)
check("edgar looks up CIK", "company_tickers.json" in edgar_src)

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
