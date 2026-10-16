# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 152 smoke - provider tool-support flag."""
from pathlib import Path
import ast, os, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 152: provider tool-support flag ===")

pt = (SRC / "providers.py").read_text(encoding="utf-8")
lt = (SRC / "llm.py").read_text(encoding="utf-8")

check("providers.py has supports_tools field",
      "supports_tools: bool = True" in pt)
check("providers.py sets pollinations False",
      'name.lower() != "pollinations"' in pt)
check("providers.py status exposes flag",
      '"supports_tools": self.supports_tools' in pt)
check("llm.py strips tools when unsupported",
      'tools if getattr(p, "supports_tools", True) else None' in lt)

# Verify by loading providers with LLM_PROVIDERS forced
sys.path.insert(0, str(SRC.parent))

# Test the parse logic: temporarily set the env so multi-provider path is used
saved = os.environ.get("LLM_PROVIDERS")
os.environ["LLM_PROVIDERS"] = "groq,gemini,openrouter,pollinations"
os.environ.setdefault("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
os.environ.setdefault("GROQ_MODEL", "x")
os.environ.setdefault("GEMINI_BASE_URL", "https://x/v1")
os.environ.setdefault("GEMINI_MODEL", "x")
os.environ.setdefault("OPENROUTER_BASE_URL", "https://x/v1")
os.environ.setdefault("OPENROUTER_MODEL", "x")
os.environ.setdefault("POLLINATIONS_BASE_URL", "https://x/v1")
os.environ.setdefault("POLLINATIONS_MODEL", "x")

from sunnyware import providers as P
P.reset_for_tests()
provs = P.load_providers(reload=True)
by_name = {p.name: p for p in provs}

if "pollinations" in by_name:
    check("pollinations.supports_tools = False",
          by_name["pollinations"].supports_tools is False)
    pol_status = by_name["pollinations"].status()
    check("pollinations.status() has supports_tools",
          pol_status.get("supports_tools") is False)
else:
    check("pollinations.supports_tools = False",
          False, "pollinations not loaded — env issue")
    check("pollinations.status() has supports_tools", False, "n/a")

if "groq" in by_name:
    check("groq.supports_tools = True",
          by_name["groq"].supports_tools is True)
else:
    check("groq.supports_tools = True", False, "groq not loaded")

# Cleanup env
P.reset_for_tests()
if saved is None:
    os.environ.pop("LLM_PROVIDERS", None)
else:
    os.environ["LLM_PROVIDERS"] = saved

for fp in [SRC / "providers.py", SRC / "llm.py"]:
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
