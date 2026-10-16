# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 161 smoke - tamper-evident audit trail."""
from pathlib import Path
import ast, json, os, sys, tempfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 161: audit trail ===")

ap = SRC / "audit.py"
check("audit.py exists", ap.exists())
at = ap.read_text(encoding="utf-8") if ap.exists() else ""
for fn in ("def log(", "def verify_all(", "def recent(",
           "def stats(", "def sign(", "def clear("):
    check(f"has {fn}", fn in at)
check("safe exception handling", "except Exception:" in at)

mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("wraps _check_admin", "_ORIG_CHECK_ADMIN" in mt)
for ep in ('"/api/audit/recent"', '"/api/audit/stats"',
           '"/api/audit/verify"', '"/api/audit/export"',
           '"/api/audit/clear"'):
    check(f"has endpoint {ep}", ep in mt)

tmpd = Path(tempfile.mkdtemp(prefix="audit_smoke_"))
logp = tmpd / "audit_log.jsonl"
os.environ["SUNNYWARE_AUDIT_PATH"] = str(logp)
os.environ["SUNNYWARE_AUDIT_ENABLED"] = "1"
os.environ["SUNNYWARE_AUDIT_KEY"] = "smoke-key-abc123"

sys.path.insert(0, str(SRC.parent))
from sunnyware import audit as A

check("enabled()", A.enabled() is True)
check("path() override", str(A.path()) == str(logp))

sample = {"ts": 1.0, "action": "x", "actor": "y", "ok": True,
          "detail": "", "prev": A._ZERO_HASH}
h1 = A.sign(sample)
h2 = A.sign(sample)
check("sign() deterministic", h1 == h2 and len(h1) == 64)

os.environ["SUNNYWARE_AUDIT_KEY"] = "other-key"
h3 = A.sign(sample)
check("sign() key-sensitive", h3 != h1)
os.environ["SUNNYWARE_AUDIT_KEY"] = "smoke-key-abc123"

e1 = A.log("test.action", actor="alice", ok=True, detail="hello",
           extra_field="v")
check("log() returns dict", isinstance(e1, dict))
check("log() has sig", isinstance(e1.get("sig"), str))
check("log() prev=zero first", e1.get("prev") == A._ZERO_HASH)
check("file created", logp.exists())
check("file has 1 line",
      len(logp.read_text(encoding="utf-8").splitlines()) == 1)

e2 = A.log("test.action2", actor="bob", ok=False, detail="nope")
check("second.prev == first.sig", e2.get("prev") == e1.get("sig"))

e3 = A.log("test.action3", actor="carol", ok=True)
check("third.prev == second.sig", e3.get("prev") == e2.get("sig"))

v = A.verify_all()
check("verify ok=True", v["ok"] is True)
check("verify count=3", v["count"] == 3)
check("verify first_bad None", v["first_bad_index"] is None)

r = A.recent(2)
check("recent(2) returns 2", len(r) == 2)
check("recent newest last", r[-1]["action"] == "test.action3")

s = A.stats()
check("stats.total=3", s["total"] == 3)
check("stats.allow>=2", s["allow"] >= 2)
check("stats.deny>=1", s["deny"] >= 1)
check("stats.by_action has key",
      "test.action" in s["by_action"])

raw = logp.read_text(encoding="utf-8").splitlines()
tampered = json.loads(raw[1])
tampered["actor"] = "attacker"
raw[1] = json.dumps(tampered, sort_keys=True)
logp.write_text("\n".join(raw) + "\n", encoding="utf-8")

v2 = A.verify_all()
check("tamper detected -> ok False", v2["ok"] is False)
check("tamper detected at index 1", v2["first_bad_index"] == 1)
check("tamper reason signature mismatch",
      v2["reason"] == "signature mismatch")

A.clear()
check("clear removed file", not logp.exists())
A.log("after.clear", actor="dave", ok=True)
v3 = A.verify_all()
check("fresh log verifies", v3["ok"] is True and v3["count"] == 1)

os.environ["SUNNYWARE_AUDIT_ENABLED"] = "0"
n_before = len(logp.read_text(encoding="utf-8").splitlines())
A.log("should.not.write", actor="eve", ok=True)
n_after = len(logp.read_text(encoding="utf-8").splitlines())
check("disabled -> no writes", n_before == n_after)
check("disabled -> enabled() False", A.enabled() is False)
os.environ["SUNNYWARE_AUDIT_ENABLED"] = "1"

A.log("weird.action", actor="frank", ok=True,
      obj={"nested": [1, 2, 3]}, bignum=12345)
v4 = A.verify_all()
check("still verifies after extras", v4["ok"] is True)

for fp in [ap, SRC / "routes" / "meta.py"]:
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
