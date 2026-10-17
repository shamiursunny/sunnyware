# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 174: container-aware hardware resource metrics.

Reads CPU/RAM limits from cgroup v2/v1 first, falls back to psutil,
falls back to env, falls back to hardcoded HF free-tier defaults.
This avoids the classic psutil-in-Docker bug where virtual_memory()
reports the host's 500GB instead of the container's 16GB.

Sampling: one call every SUNNYWARE_METRICS_INTERVAL_S (default 5s).
Storage: in-memory deque(720 slots = 1h rolling window).
"""

import os
import time
from collections import deque
from typing import Optional


LIVE_BUFFER_SIZE = 720  # 1h at 5s/sample
_BUFFER = deque(maxlen=LIVE_BUFFER_SIZE)
_LAST_CPU_PCT: Optional[float] = None
_LAST_SAMPLE_TS: float = 0.0
_SAMPLE_MIN_INTERVAL = 4.0  # seconds


def _read_cgroup_mem() -> tuple:
    """Return (limit_bytes, source) or (None, None)."""
    for p in ("/sys/fs/cgroup/memory.max",
              "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(p) as f:
                v = f.read().strip()
                if v and v != "max":
                    n = int(v)
                    if 0 < n < (1 << 62):
                        return n, "cgroup"
        except Exception:
            pass
    return None, None


def _read_cgroup_cpu_count() -> tuple:
    """Return (cpu_count_float, source) or (None, None)."""
    # cgroups v2
    try:
        with open("/sys/fs/cgroup/cpu.max") as f:
            parts = f.read().split()
            if len(parts) == 2 and parts[0] != "max":
                return int(parts[0]) / int(parts[1]), "cgroup"
    except Exception:
        pass
    # cgroups v1
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
            q = int(f.read())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
            p = int(f.read())
        if q > 0 and p > 0:
            return q / p, "cgroup"
    except Exception:
        pass
    return None, None


def _enumerate_disks() -> list:
    """Enumerate real disk mounts. Filters pseudo-FS, dedupes by device."""
    import psutil
    PSEUDO = {
        "tmpfs", "devtmpfs", "proc", "sysfs", "cgroup", "cgroup2",
        "mqueue", "devpts", "hugetlbfs", "debugfs", "tracefs",
        "securityfs", "pstore", "bpf", "configfs", "fusectl",
        "squashfs", "overlay", "aufs",
    }
    seen = set()
    mounts = []
    try:
        parts = psutil.disk_partitions(all=False)
    except Exception:
        return mounts
    for p in parts:
        if p.fstype in PSEUDO:
            continue
        if p.device in seen:
            continue
        try:
            u = psutil.disk_usage(p.mountpoint)
        except Exception:
            continue
        seen.add(p.device)
        path = p.mountpoint
        role = ("root" if path == "/"
                else "data" if path == "/data" or path.startswith("/data/")
                else "other")
        persistent = (
            os.getenv("SUNNYWARE_DATA_PERSISTENT") == "1"
            and role == "data"
        )
        mounts.append({
            "path": path,
            "device": p.device,
            "fstype": p.fstype,
            "total_bytes": int(u.total),
            "used_bytes": int(u.used),
            "free_bytes": int(u.free),
            "percent": round(u.percent, 1),
            "role": role,
            "persistent": persistent,
        })
    return mounts


def limits() -> dict:
    """Resolve hardware limits via cgroup -> psutil -> env -> default."""
    import psutil

    mem_total, mem_src = _read_cgroup_mem()
    if mem_total is None:
        try:
            mem_total = int(psutil.virtual_memory().total)
            mem_src = "psutil"
        except Exception:
            mem_total = int(os.getenv("SUNNYWARE_CONTAINER_MEM_GB", "16")) * (1 << 30)
            mem_src = "env"

    cpu_count, cpu_src = _read_cgroup_cpu_count()
    if cpu_count is None:
        try:
            cpu_count = float(psutil.cpu_count() or 2)
            cpu_src = "psutil"
        except Exception:
            cpu_count = float(os.getenv("SUNNYWARE_CONTAINER_VCPU", "2"))
            cpu_src = "env"

    return {
        "cpu_count": round(cpu_count, 2),
        "cpu_source": cpu_src,
        "mem_total_bytes": int(mem_total),
        "mem_source": mem_src,
    }


def sample_once() -> None:
    """Take one sample, append to rolling buffer. Called by background task."""
    global _LAST_CPU_PCT
    import psutil
    try:
        pct = psutil.cpu_percent(interval=None)
    except Exception:
        pct = 0.0
    try:
        vm = psutil.virtual_memory()
        mem_used = int(vm.used)
        cg_mem, _ = _read_cgroup_mem()
        if cg_mem and cg_mem < vm.total:
            mem_used = min(mem_used, cg_mem)
    except Exception:
        mem_used = 0

    global _LAST_SAMPLE_TS
    _BUFFER.append({
        "ts": time.time(),
        "cpu_pct": round(pct, 2),
        "mem_used_bytes": mem_used,
    })
    _LAST_CPU_PCT = pct
    _LAST_SAMPLE_TS = time.time()


def _stats(key: str) -> dict:
    vals = [s[key] for s in _BUFFER if s.get(key) is not None]
    if not vals:
        return {"min": None, "max": None, "avg": None, "samples": 0}
    return {
        "min": round(min(vals), 2),
        "max": round(max(vals), 2),
        "avg": round(sum(vals) / len(vals), 2),
        "samples": len(vals),
    }


def snapshot() -> dict:
    """Full snapshot: limits, current, ranges, disk list."""
    import psutil
    global _LAST_SAMPLE_TS
    now_ts = time.time()
    if now_ts - _LAST_SAMPLE_TS >= _SAMPLE_MIN_INTERVAL:
        try:
            sample_once()
        except Exception:
            pass

    lim = limits()
    vm = psutil.virtual_memory()
    mem_total = lim["mem_total_bytes"]
    mem_used = min(vm.used, mem_total) if mem_total else vm.used
    mem_pct = round((mem_used / mem_total * 100) if mem_total > 0 else 0, 1)

    disks = _enumerate_disks()
    disk_total = sum(d["total_bytes"] for d in disks)
    disk_used = sum(d["used_bytes"] for d in disks)
    disk_free = sum(d["free_bytes"] for d in disks)
    disk_pct = round((disk_used / disk_total * 100)
                     if disk_total > 0 else 0.0, 1)

    return {
        "limits": lim,
        "current": {
            "cpu_pct": round(_LAST_CPU_PCT or 0.0, 2),
            "cpu_count": lim["cpu_count"],
            "mem_used_bytes": int(mem_used),
            "mem_total_bytes": int(mem_total),
            "mem_pct": mem_pct,
            "disks": disks,
            "disk_aggregate": {
                "total_bytes": int(disk_total),
                "used_bytes": int(disk_used),
                "free_bytes": int(disk_free),
                "percent": disk_pct,
            },
        },
        "ranges": {
            "1h": {
                "cpu": _stats("cpu_pct"),
                "mem_used_bytes": _stats("mem_used_bytes"),
                "samples": len(_BUFFER),
            }
        },
        "buffer": {
            "size": len(_BUFFER),
            "capacity": LIVE_BUFFER_SIZE,
        },
    }
