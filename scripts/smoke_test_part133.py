# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 133 smoke test - prompt externalization."""
from pathlib import Path
import ast, json, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 133: prompt externalization ===")

# 1. prompts.json exists + valid JSON + has roles block
pj = SRC / "static" / "prompts.json"
check("static/prompts.json exists", pj.exists())
try:
    data = json.loads(pj.read_text(encoding="utf-8"))
    check("prompts.json parses", True)
except Exception as e:
    check("prompts.json parses", False, str(e))
    data = {}
check("prompts.json has version", isinstance(data.get("version"), int))
check("prompts.json has roles block",
      isinstance(data.get("roles"), dict))
check("prompts.json has 8+ role entries",
      len(data.get("roles", {})) >= 8,
      f"n={len(data.get('roles', {}))}")
for role_key in ("fpa", "quant", "actuary", "tax", "cfo", "cdo",
                 "legal", "risk_ins"):
    entry = (data.get("roles") or {}).get(role_key) or {}
    check(f"prompts.json has '{role_key}'",
          "prompt_addon" in entry)

# 2. roles.py has loader
rp = (SRC / "roles.py").read_text(encoding="utf-8")
check("roles.py has _load_external_prompts",
      "def _load_external_prompts" in rp)
check("roles.py has _external_status",
      "def _external_status" in rp)
check("roles.py calls loader at import",
      "_load_external_prompts(_EXTERNAL_PROMPTS_PATH)" in rp)
check("roles.py imports json",
      "import json" in rp or "import json as" in rp)

# 3. Loader actually ran
sys.path.insert(0, str(SRC.parent))
from sunnyware import roles as R

status = R._external_status()
check("loader source is 'external'", status["source"] == "external",
      status["source"])
check("loader version >= 1", status["version"] >= 1)
check("loader path is static/prompts.json",
      status["path"].endswith("prompts.json"))

# 4. Addons preserved
for k in ("legal", "risk_ins", "actuary", "fpa", "cfo", "cdo"):
    a = R.ROLES[k].get("prompt_addon") or ""
    check(f"role '{k}' has non-empty addon", len(a) > 50, f"len={len(a)}")

legal = R.prompt_addon("legal")
check("legal addon has PRIVILEGED marker", "PRIVILEGED" in legal)
check("legal addon has 'not legal advice'",
      "not legal advice" in legal.lower())
check("legal addon has 'attorney review'",
      "attorney review" in legal.lower())

risk = R.prompt_addon("risk_ins")
check("risk_ins addon has VaR", "VaR" in risk)
check("risk_ins addon has chainladder", "chainladder" in risk)
check("risk_ins addon has 'confidence'",
      "confidence" in risk.lower())

fpa = R.prompt_addon("fpa")
check("fpa addon mentions edgar",
      "edgar" in fpa.lower() or "fmp" in fpa.lower())

# 5. Reload is idempotent
n1, err1 = R._load_external_prompts()
n2, err2 = R._load_external_prompts()
check("reload #1 returns loaded count",
      isinstance(n1, int) and n1 >= 8, f"n={n1}")
check("reload #2 same count", n1 == n2)
check("reload returns no error",
      err1 is None and err2 is None, str(err1 or err2))

# 6. Endpoints wired
routes = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("GET /api/prompts exists",
      '@router.get("/api/prompts")' in routes)
check("GET /api/prompts/status exists",
      '@router.get("/api/prompts/status")' in routes)
check("POST /api/prompts/reload exists",
      '@router.post("/api/prompts/reload")' in routes)

# 7. Missing-file resilience: temp-dir test
import tempfile
with tempfile.TemporaryDirectory() as td:
    bogus = Path(td) / "nope.json"
    n, err = R._load_external_prompts(bogus)
    check("missing file -> 0 loaded, no error",
          n == 0 and err is None)

# 8. Corrupt-file resilience
with tempfile.TemporaryDirectory() as td:
    bogus = Path(td) / "bad.json"
    bogus.write_text("{ this is not json", encoding="utf-8")
    n, err = R._load_external_prompts(bogus)
    check("corrupt file -> 0 loaded, error returned",
          n == 0 and isinstance(err, str))

# 9. Files parse
for fp in [SRC / "roles.py", SRC / "routes" / "meta.py"]:
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
