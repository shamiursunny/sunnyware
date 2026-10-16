# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 153 smoke - cooldown preservation + pollinations floor."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 153 ===")

lt = (SRC / "llm.py").read_text(encoding="utf-8")
ct = (SRC / "provider_limits_config.py").read_text(encoding="utf-8")
mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")

check("llm.py: reload fix", "Part 153: DO NOT reload" in lt)
check("plc.py: pollinations floor", "Part 153: pollinations IP cap" in ct)
check("meta.py: cooldowns endpoint",
      "/api/providers/cooldowns" in mt)

sys.path.insert(0, str(SRC.parent))
from sunnyware import provider_limits_config as PLC

cd = PLC.compute_cooldown("pollinations", "HTTP 402 FREE_LIMIT")
check("pollinations 402 -> 35s", cd == 35.0, "got=%s" % cd)

cd2 = PLC.compute_cooldown(
    "pollinations",
    '{"code":"FREE_LIMIT","message":"Retry after 22s"}')
check("pollinations 402 w/ hint -> 27s", cd2 == 27.0, "got=%s" % cd2)

for fp in [SRC / "llm.py", SRC / "provider_limits_config.py",
           SRC / "routes" / "meta.py"]:
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
