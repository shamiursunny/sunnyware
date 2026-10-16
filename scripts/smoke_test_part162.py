# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 162 smoke - recon-path guard."""
from pathlib import Path
import ast, os, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 162: recon-path guard ===")

rp = SRC / "recon_guard.py"
check("recon_guard.py exists", rp.exists())
rt = rp.read_text(encoding="utf-8") if rp.exists() else ""
for fn in ("def check(", "def record(", "def stats(",
           "def reset(", "def enabled("):
    check(f"has {fn}", fn in rt)
check("safe exception handling", "except Exception:" in rt)

mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("has GET /api/recon/stats", '"/api/recon/stats"' in mt)
check("has POST /api/recon/reset", '"/api/recon/reset"' in mt)

mp = SRC / "main.py"
check("main.py exists", mp.exists())
at = mp.read_text(encoding="utf-8")
check("middleware present", "_recon_guard_middleware" in at)
check("403 status", "status_code=403" in at)

sys.path.insert(0, str(SRC.parent))
os.environ["SUNNYWARE_RECON_GUARD_ENABLED"] = "1"
os.environ["SUNNYWARE_RECON_LOG_TO_AUDIT"] = "0"
from sunnyware import recon_guard as RG

check("enabled()", RG.enabled() is True)

allowed_paths = [
    "/api/chat",
    "/api/health",
    "/health/ready",
    "/static/x.js",
    "/docs",
    "/openapi.json",
    "/favicon.ico",
    "/.well-known/acme-challenge/xyz",
]
all_ok = True
for p in allowed_paths:
    if RG.check(p).get("block"):
        all_ok = False
        print(f"    ! unexpectedly blocked: {p}")
check("allowed paths not blocked", all_ok)

blocked_paths = [
    "/.env",
    "/.env.local",
    "/.git/config",
    "/.git/HEAD",
    "/wp-admin/",
    "/wp-login.php",
    "/xmlrpc.php",
    "/phpmyadmin/index.php",
    "/adminer.php",
    "/cgi-bin/luci",
    "/shell.php",
    "/c99.php",
    "/backup.sql",
    "/dump.sql",
    "/.aws/credentials",
    "/.DS_Store",
]
all_blocked = True
for p in blocked_paths:
    d = RG.check(p)
    if not d.get("block"):
        all_blocked = False
        print(f"    ! NOT blocked: {p}")
check("probe paths blocked", all_blocked)

os.environ["SUNNYWARE_RECON_GUARD_ENABLED"] = "0"
check("disabled: /.env allowed",
      RG.check("/.env").get("block") is False)
os.environ["SUNNYWARE_RECON_GUARD_ENABLED"] = "1"

RG.reset()
check("fresh reset -> total 0", RG.stats()["blocked_total"] == 0)
RG.record("/.env", ip="1.2.3.4", pattern=r"/\.env(\.|$|/|$)")
RG.record("/wp-admin/", ip="1.2.3.4", pattern=r"/wp-admin($|/)")
RG.record("/shell.php", ip="5.6.7.8", pattern=r"\.php$")
s = RG.stats()
check("blocked_total=3", s["blocked_total"] == 3)
check("by_pattern has 3", len(s["by_pattern"]) == 3)
check("by_ip_top[0]=(1.2.3.4,2)",
      s["by_ip_top"] and s["by_ip_top"][0] == ("1.2.3.4", 2))
check("last_path=/shell.php", s["last_path"] == "/shell.php")
check("last_ip=5.6.7.8", s["last_ip"] == "5.6.7.8")
check("first_ts set", s["first_ts"] is not None)
check("recent has 3", len(s["recent"]) == 3)
check("recent order preserved",
      s["recent"][-1]["path"] == "/shell.php")

prev = RG.reset()
check("reset returns prev=3", prev == 3)
check("after reset total=0", RG.stats()["blocked_total"] == 0)

os.environ["SUNNYWARE_RECON_RECENT_MAX"] = "5"
RG.reset()
for i in range(10):
    RG.record(f"/probe_{i}.php", ip="9.9.9.9", pattern=r"\.php$")
check("recent capped at 5", len(RG.stats()["recent"]) == 5)
check("recent kept the newest",
      RG.stats()["recent"][-1]["path"] == "/probe_9.php")
os.environ.pop("SUNNYWARE_RECON_RECENT_MAX", None)

for fp in [rp, SRC / "routes" / "meta.py", mp]:
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
