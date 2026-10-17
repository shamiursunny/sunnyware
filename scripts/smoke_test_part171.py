# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 171 smoke - outbound webhooks."""
from pathlib import Path
import ast, os, sys, tempfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 171: outbound webhooks ===")

wp = SRC / "webhooks_out.py"
check("webhooks_out.py exists", wp.exists())
wt = wp.read_text(encoding="utf-8") if wp.exists() else ""
for fn in ("def subscribe(", "def unsubscribe(", "def list_all(",
           "def recent(", "def dispatch(", "def _deliver(",
           "def _sign(", "def _matches(", "def test_fire(",
           "def reset("):
    check(f"has {fn}", fn in wt)

check("uses HMAC signature", "_sign(" in wt and "hmac.new" in wt)
check("retries 3 times", "attempt < 3" in wt and "backoff" in wt)
check("fire-and-forget dispatch", "loop.create_task" in wt)
check("5s subscriber cache", "_CACHE_TTL = 5" in wt)
check("delivery log capped", "_DELIVERY_LOG_CAP" in wt)

at = (SRC / "audit.py").read_text(encoding="utf-8")
check("audit.py dispatches to webhooks",
      "Part 171: mirror every audit entry" in at)
check("audit.py imports webhooks_out",
      "from . import webhooks_out as _wo" in at)

ct = (SRC / "circuit_breaker.py").read_text(encoding="utf-8")
check("circuit_breaker emits circuit.open",
      "Part 171: emit circuit.open event" in ct)
check("circuit_breaker calls audit.log",
      "audit.log(" in ct and "circuit.open" in ct)

mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
for ep in ('"/api/webhooks-out/subscribe"',
           '"/api/webhooks-out/list"',
           '"/api/webhooks-out/unsubscribe"',
           '"/api/webhooks-out/recent"',
           '"/api/webhooks-out/test/{webhook_id}"'):
    check(f"endpoint {ep}", ep in mt)

tmpdir = tempfile.mkdtemp(prefix="wh171_")
os.environ["SUNNYWARE_WEBHOOKS_OUT_STORAGE"] = \
    os.path.join(tmpdir, "wh.json")
os.environ["SUNNYWARE_WEBHOOKS_OUT_ENABLED"] = "1"

sys.path.insert(0, str(SRC.parent))
from sunnyware import webhooks_out as WO

WO.reset()
check("reset -> empty list", WO.list_all()["count"] == 0)

r = WO.subscribe("not-a-url", ["test"])
check("rejects non-http url", r.get("ok") is False)
check("error mentions url", "url" in r.get("error", "").lower())

r = WO.subscribe("https://example.com/hook", [])
check("rejects empty events", r.get("ok") is False)

r = WO.subscribe(
    "https://example.com/hook",
    ["circuit.open", "audit.*"],
    description="Test subscriber",
)
check("valid subscribe ok", r.get("ok") is True)
wh = r["webhook"]
check("returns id", bool(wh.get("id")))
check("returns secret ONCE", bool(wh.get("secret")))
check("secret is long enough", len(wh.get("secret", "")) >= 24)
check("events stored", wh["events"] == ["circuit.open", "audit.*"])
wid = wh["id"]
secret = wh["secret"]

lst = WO.list_all()
check("list shows 1", lst["count"] == 1)
check("list redacts secret",
      "secret" not in (lst["webhooks"][0]))
check("list preserves id",
      lst["webhooks"][0]["id"] == wid)

body = b'{"event":"x"}'
s1 = WO._sign(secret, body)
s2 = WO._sign(secret, body)
check("signature deterministic", s1 == s2)
check("signature is 64 hex chars",
      len(s1) == 64 and all(c in "0123456789abcdef" for c in s1))
s3 = WO._sign("other-secret", body)
check("signature key-sensitive", s3 != s1)

spec_match = {"events": ["circuit.open"]}
check("exact match",
      WO._matches(spec_match, "circuit.open") is True)
check("no match when different",
      WO._matches(spec_match, "audit.log") is False)

spec_wild = {"events": ["audit.*"]}
check("wildcard prefix match",
      WO._matches(spec_wild, "audit.log") is True)
check("wildcard prefix miss",
      WO._matches(spec_wild, "circuit.open") is False)

spec_all = {"events": ["*"]}
check("wildcard all matches",
      WO._matches(spec_all, "anything.at.all") is True)

try:
    WO.dispatch("audit.log", {"x": 1})
    check("dispatch outside loop is safe", True)
except Exception as e:
    check("dispatch outside loop is safe", False, str(e))

r = WO.unsubscribe(wid)
check("unsubscribe ok", r.get("ok") is True)
check("list empty after unsubscribe",
      WO.list_all()["count"] == 0)

os.environ["SUNNYWARE_WEBHOOKS_OUT_ENABLED"] = "0"
check("disabled -> list_all shows enabled=False",
      WO.list_all()["enabled"] is False)
WO.dispatch("anything", {})
check("disabled dispatch safe", True)
os.environ["SUNNYWARE_WEBHOOKS_OUT_ENABLED"] = "1"

for fp in [wp, SRC / "audit.py", SRC / "circuit_breaker.py",
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
