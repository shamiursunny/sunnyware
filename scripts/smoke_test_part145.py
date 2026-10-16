# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 145 smoke - reset-aware cooldown."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 145: reset-aware cooldown ===")

cp = SRC / "provider_limits_config.py"
check("provider_limits_config.py exists", cp.exists())
ct = cp.read_text(encoding="utf-8")
check("has FREE_TIER_LIMITS", "FREE_TIER_LIMITS" in ct)
check("has compute_cooldown", "def compute_cooldown" in ct)
check("has seconds_until_next_reset", "def seconds_until_next_reset" in ct)
check("has _classify", "def _classify" in ct)

lt = (SRC / "llm.py").read_text(encoding="utf-8")
check("llm.py imports plc", "import provider_limits_config as _plc" in lt)
check("llm.py uses compute_cooldown",
      "Part 143 + 145: provider + error-type aware cooldown" in lt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import provider_limits_config as PLC

for prov in ("groq", "gemini", "openrouter", "pollinations"):
    check(f"config has {prov}", prov in PLC.FREE_TIER_LIMITS)

check("groq rpm=30", PLC.FREE_TIER_LIMITS["groq"]["rpm"] == 30)
check("groq rpd=1000", PLC.FREE_TIER_LIMITS["groq"]["rpd"] == 1000)
check("gemini reset_kind=pacific",
      PLC.FREE_TIER_LIMITS["gemini"]["reset_kind"] == "pacific")
check("openrouter rpd=50",
      PLC.FREE_TIER_LIMITS["openrouter"]["rpd"] == 50)
check("pollinations has no reset",
      PLC.FREE_TIER_LIMITS["pollinations"]["reset_kind"] == "none")

check("classify: 'requests per day' -> per_day",
      PLC._classify("Rate limit reached on requests per day (RPD)") == "per_day")
check("classify: 'RPD' -> per_day",
      PLC._classify("RPD exhausted") == "per_day")
check("classify: 'per minute' -> per_minute",
      PLC._classify("rate limit on requests per minute") == "per_minute")
check("classify: 'TPM' -> per_minute",
      PLC._classify("TPM exceeded") == "per_minute")
check("classify: nonsense -> unknown",
      PLC._classify("some random error") == "unknown")
check("classify: empty -> unknown",
      PLC._classify("") == "unknown")

cd = PLC.compute_cooldown("groq", "Retry after 8s. Request too many.")
check("retry hint honored (8+5=13s)", 12.5 <= cd <= 13.5, f"cd={cd}")

cd = PLC.compute_cooldown("groq", "rate limit reached on requests per minute")
check("per-minute -> ~65s", 60.0 <= cd <= 70.0, f"cd={cd}")

cd = PLC.compute_cooldown("groq", "rate limit reached on requests per day")
check("per-day groq -> up to 25h", 30.0 < cd <= 25 * 3600.0, f"cd={cd}")

cd = PLC.compute_cooldown("gemini", "quota exceeded per day")
check("per-day gemini -> 30s..25h", 30.0 < cd <= 25 * 3600.0, f"cd={cd}")

cd = PLC.compute_cooldown("pollinations", "per day limit")
check("per-day pollinations -> 3600s", 3500 < cd <= 3700, f"cd={cd}")

cd = PLC.compute_cooldown("groq", "something odd")
check("unknown -> 60s default", 55 <= cd <= 65, f"cd={cd}")

s = PLC.seconds_until_next_reset("groq")
check("groq reset secs in 0..86400", 0 <= s <= 86400, f"s={int(s)}")

s = PLC.seconds_until_next_reset("gemini")
check("gemini reset secs in 0..86400", 0 <= s <= 86400, f"s={int(s)}")

s = PLC.seconds_until_next_reset("pollinations")
check("pollinations reset secs == 0", s == 0)

s = PLC.seconds_until_next_reset("unknown-provider")
check("unknown provider -> 0", s == 0)

snap = PLC.snapshot()
check("snapshot has providers", "providers" in snap)
check("snapshot lists all 4", len(snap["providers"]) == 4)
check("snapshot has sources", "sources" in snap)

for fp in [cp, SRC / "llm.py"]:
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
