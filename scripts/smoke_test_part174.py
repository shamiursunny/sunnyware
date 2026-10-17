# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 174 smoke - hardware resources + Neon storage."""
from pathlib import Path
import ast, os, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail else ""))

print("=== Part 174: hardware resources + Neon storage ===")

# system_metrics.py
smp = SRC / "system_metrics.py"
check("system_metrics.py exists", smp.exists())
st = smp.read_text(encoding="utf-8") if smp.exists() else ""
for fn in ("def snapshot(", "def sample_once(", "def limits(",
           "def _read_cgroup_mem(", "def _read_cgroup_cpu_count(",
           "def _enumerate_disks("):
    check(f"has {fn}", fn in st)
check("uses cgroup v2 memory", "/sys/fs/cgroup/memory.max" in st)
check("uses cgroup v2 cpu", "/sys/fs/cgroup/cpu.max" in st)
check("falls back to psutil", "psutil.virtual_memory" in st)
check("enumerates disks", "psutil.disk_partitions" in st)
check("filters pseudo FS", "tmpfs" in st and "overlay" in st)
check("dedupes by device", "seen.add(p.device)" in st)
check("self-sampling", "_LAST_SAMPLE_TS" in st)
check("clamps mem to cgroup limit",
      "if mem_total > 0 and mem_used > mem_total:" in st)
check("uses process tree RSS", "def _process_tree_mem(" in st)
check("mem.current cgroup read",
      "/sys/fs/cgroup/memory.current" in st)
check("filters bind mounts",
      "FORBIDDEN_PREFIXES" in st and "/etc/" in st)
check("filters absurd disk sizes",
      "500 * (1 << 30)" in st)
check("data-nvme classified as data",
      "/data-nvme" in st)
check("limits fall back to env not psutil",
      'mem_src = "default"' in st)

# meta.py wiring
mt = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("meta.py: neon queries size",
      "pg_database_size(current_database())" in mt)
check("meta.py: neon storage fields", '"used_mb"' in mt and '"free_mb"' in mt)
check("meta.py: resources_snapshot helper",
      "async def resources_snapshot(" in mt)
check("meta.py: summary wires resources",
      'await _safe("resources", resources_snapshot)' in mt)
check("meta.py: limit env var",
      "SUNNYWARE_NEON_STORAGE_LIMIT_MB" in mt)

# status.html
sh = (ROOT / "static" / "status.html").read_text(encoding="utf-8")
check("status.html: resources card", 'id:"resources"' in sh)
check("status.html: renderResources", "function renderResources(" in sh)
check("status.html: fmtBytes helper", "function fmtBytes(" in sh)
check("status.html: Neon storage bar", "Part 174: Neon DB storage bar" in sh)
check("status.html: shows CPU bar", 'bar("CPU"' in sh)
check("status.html: shows RAM bar", 'bar("RAM"' in sh)
check("status.html: shows DISK bar", 'bar("DISK"' in sh)
check("status.html: per-mount rows", "disks.length > 1" in sh)
check("status.html: 1h cpu stats", "1h CPU:" in sh)

# Functional test - real snapshot
sys.path.insert(0, str(SRC.parent))
try:
    os.environ["SUNNYWARE_NEON_STORAGE_LIMIT_MB"] = "512"
    from sunnyware import system_metrics as SM
    snap = SM.snapshot()
    check("snapshot returns dict", isinstance(snap, dict))
    check("has limits", "limits" in snap)
    check("has current", "current" in snap)
    check("has ranges", "ranges" in snap)
    check("has 1h range", "1h" in (snap.get("ranges") or {}))
    lim = snap.get("limits") or {}
    check("cpu_count > 0", (lim.get("cpu_count") or 0) > 0)
    check("mem_total > 0", (lim.get("mem_total_bytes") or 0) > 0)
    check("cpu_source set", bool(lim.get("cpu_source")))
    check("mem_source set", bool(lim.get("mem_source")))
    cur = snap.get("current") or {}
    check("cpu_pct is number", isinstance(cur.get("cpu_pct"), (int, float)))
    check("mem_pct is number", isinstance(cur.get("mem_pct"), (int, float)))
    check("disks is list", isinstance(cur.get("disks"), list))
    check("disk_aggregate present", "disk_aggregate" in cur)
except Exception as e:
    check("snapshot executes cleanly", False, str(e))

# Files parse
for fp in [smp, SRC / "routes" / "meta.py", SRC / "main.py"]:
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
