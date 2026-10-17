# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 169 smoke - prompt A/B testing."""
from pathlib import Path
import ast, os, sys, tempfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 169: prompt A/B testing ===")

# ─── File presence ───
ap = SRC / "ab_testing.py"
check("ab_testing.py exists", ap.exists())
at = ap.read_text(encoding="utf-8") if ap.exists() else ""
for fn in ("def create(", "def list_all(", "def results(",
           "def delete(", "def pick_variant(",
           "def _bucket(", "def _load(", "def _save("):
    check(f"has {fn}", fn in at)

# ─── Orchestrator wired ───
ot = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator wires A/B",
      "Part 169: A/B prompt experiment injection" in ot)
check("orchestrator calls pick_variant",
      "pick_variant(" in ot)
check("orchestrator injects arm b extra",
      'if _ab_arm == "b"' in ot)
check("A/B wired AFTER role addon",
      ot.find("Part 169") > ot.find("Part 112"))
check("A/B wired BEFORE final system override",
      ot.find("Part 169") < ot.find('if system:\n        system_prompt = system'))

# ─── Endpoints ───
mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
for ep in ('"/api/ab/create"', '"/api/ab/list"',
           '"/api/ab/results/{exp_id}"', '"/api/ab/delete"'):
    check(f"endpoint {ep}", ep in mt)

# ─── Functional tests ───
tmpdir = tempfile.mkdtemp(prefix="ab_smoke_")
os.environ["SUNNYWARE_AB_STORAGE"] = os.path.join(tmpdir, "ab.json")
os.environ["SUNNYWARE_AB_ENABLED"] = "1"

sys.path.insert(0, str(SRC.parent))
from sunnyware import ab_testing as AB

AB.reset()
check("reset leaves no experiments",
      len(AB.list_all()["experiments"]) == 0)

# Create experiment
r = AB.create(name="test-1", role="*", split_pct=50,
              prompt_b_extra="Use bullets.", active=True)
check("create returns ok", r.get("ok") is True)
check("create returns id", bool(r.get("experiment", {}).get("id")))
exp_id = r["experiment"]["id"]
check("split_pct clamped to 50",
      r["experiment"]["split_pct"] == 50)
check("role stored", r["experiment"]["role"] == "*")

# List
lst = AB.list_all()
check("list shows 1 experiment", len(lst["experiments"]) == 1)
check("list has path", bool(lst.get("path")))

# Deterministic assignment — same session gets same arm
arm1, extra1 = AB.pick_variant("sess-abc", "*")
arm2, extra2 = AB.pick_variant("sess-abc", "*")
check("deterministic: same session same arm", arm1 == arm2)
check("arm is 'a' or 'b'", arm1 in ("a", "b"))
if arm1 == "b":
    check("arm b returns extra text",
          extra1 == "Use bullets.")
else:
    check("arm a returns no extra", extra1 is None)

# Different sessions distribute
arms = set()
for i in range(50):
    a, _ = AB.pick_variant(f"session-{i}", "*")
    if a in ("a", "b"):
        arms.add(a)
check("both arms reached in 50 sessions", len(arms) == 2,
      f"arms seen: {arms}")

# Results reflects assignments
res = AB.results(exp_id)
check("results ok", res.get("ok") is True)
check("results total > 0",
      res.get("total_assignments", 0) > 0)
check("results counts sum to total",
      (res["assignments"]["a"] + res["assignments"]["b"])
      == res["total_assignments"])

# Inactive experiment is skipped
AB.reset()
AB.create(name="inactive", role="*", split_pct=50,
          prompt_b_extra="x", active=False)
arm, extra = AB.pick_variant("session-x", "*")
check("inactive experiment skipped", arm is None and extra is None)

# Role filter works
AB.reset()
AB.create(name="cfo-only", role="cfo", split_pct=0,
          prompt_b_extra="FOO", active=True)
arm, extra = AB.pick_variant("s1", "cfo")
check("role match returns arm", arm in ("a", "b"))
arm_other, extra_other = AB.pick_variant("s1", "quant")
check("role mismatch returns None",
      arm_other is None and extra_other is None)

# Delete
AB.reset()
r = AB.create(name="todelete", role="*", prompt_b_extra="", active=True)
del_id = r["experiment"]["id"]
d = AB.delete(del_id)
check("delete returns ok", d.get("ok") is True)
check("list now empty", len(AB.list_all()["experiments"]) == 0)

# Disabled mode is no-op
AB.reset()
AB.create(name="dis", role="*", prompt_b_extra="X", active=True)
os.environ["SUNNYWARE_AB_ENABLED"] = "0"
arm, extra = AB.pick_variant("s1", "*")
check("disabled -> no variant",
      arm is None and extra is None)
os.environ["SUNNYWARE_AB_ENABLED"] = "1"

# Missing name rejected
r = AB.create(name="")
check("missing name rejected", r.get("ok") is False)

# Files parse
for fp in [ap, SRC / "orchestrator.py", SRC / "routes" / "meta.py"]:
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
