# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 167 smoke - per-tool JSON schema validation."""
from pathlib import Path
import ast, os, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 167: per-tool JSON schema validation ===")

sp = SRC / "schema.py"
check("schema.py exists", sp.exists())
st = sp.read_text(encoding="utf-8") if sp.exists() else ""
for fn in ("def validate(", "def enabled(", "def strict(",
           "def _coerce("):
    check(f"schema.py has {fn}", fn in st)

ot = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator wires schema validation",
      "Part 167: JSON schema validation" in ot)
check("orchestrator calls schema.validate",
      "_schema.validate(name, _spec, args)" in ot)
check("orchestrator returns schema_violation",
      '"schema_violation"' in ot)
check("orchestrator logs to audit",
      '_audit.log(' in ot and '"schema.violation"' in ot)
check("schema runs AFTER circuit breaker",
      ot.find("Part 167") > ot.find("Part 160"))

sys.path.insert(0, str(SRC.parent))
os.environ["SUNNYWARE_SCHEMA_ENABLED"] = "1"
os.environ["SUNNYWARE_SCHEMA_STRICT"] = "1"
os.environ.pop("SUNNYWARE_SCHEMA_ALLOW_EXTRA", None)
from sunnyware import schema as S

spec = {"expression": {"type": "string", "description": "Math expr",
                       "required": True}}

r = S.validate("calculator", spec, {"expression": "2+3"})
check("valid input passes", r["ok"] is True)
check("args preserved", r["args"]["expression"] == "2+3")

r = S.validate("calculator", spec, {})
check("missing required rejects", r["ok"] is False)
check("missing detail mentions parameter",
      "missing required parameter" in r["detail"])

r = S.validate("calculator", spec, {"expression": 123})
check("int coerced to str for string field",
      r["ok"] is True and r["args"]["expression"] == "123")

spec_int = {"count": {"type": "integer", "required": True}}
r = S.validate("t", spec_int, {"count": "abc"})
check("bad int rejects in strict", r["ok"] is False)

os.environ["SUNNYWARE_SCHEMA_STRICT"] = "0"
r = S.validate("t", spec_int, {"count": "abc"})
check("bad int allowed in lenient", r["ok"] is True)
os.environ["SUNNYWARE_SCHEMA_STRICT"] = "1"

r = S.validate("calculator", spec, {"expression": "x", "bogus": "y"})
check("extra keys allowed by default", r["ok"] is True)
check("extra key warning emitted",
      any("unexpected" in w for w in r.get("warnings", [])))

os.environ["SUNNYWARE_SCHEMA_ALLOW_EXTRA"] = "0"
r = S.validate("calculator", spec, {"expression": "x", "bogus": "y"})
check("extra keys rejected when disallowed", r["ok"] is False)
os.environ.pop("SUNNYWARE_SCHEMA_ALLOW_EXTRA", None)

spec_bool = {"flag": {"type": "boolean", "required": True}}
r = S.validate("t", spec_bool, {"flag": "true"})
check("string 'true' coerces to bool",
      r["ok"] is True and r["args"]["flag"] is True)

spec_num = {"ratio": {"type": "number", "required": True}}
r = S.validate("t", spec_num, {"ratio": "3.14"})
check("string '3.14' coerces to float",
      r["ok"] is True and r["args"]["ratio"] == 3.14)

r = S.validate("noargs", {}, {"anything": "goes"})
check("empty spec bypasses", r["ok"] is True)

os.environ["SUNNYWARE_SCHEMA_ENABLED"] = "0"
r = S.validate("calculator", spec, {})
check("disabled mode bypasses", r["ok"] is True)
os.environ["SUNNYWARE_SCHEMA_ENABLED"] = "1"

r = S.validate("calculator", spec, ["not", "a", "dict"])
check("non-dict args rejected", r["ok"] is False)

for fp in [sp, SRC / "orchestrator.py"]:
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
