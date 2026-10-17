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


def _process_tree_mem() -> Optional[int]:
    """RSS of this process + all children. Best proxy for container
    memory usage when cgroup reading fails (HF Spaces case)."""
    try:
        import psutil
        proc = psutil.Process()
        total = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                total += child.memory_info().rss
            except Exception:
                pass
        return int(total)
    except Exception:
        return None


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
    # Bind mounts / host paths that psutil reports but aren't real disks
    FORBIDDEN_PREFIXES = (
        "/etc/", "/dev/", "/sys/", "/proc/", "/run/",
        "/snap/", "/var/lib/docker/", "/var/lib/containerd/",
    )
    FORBIDDEN_EXACT = (
        "/etc/hosts", "/etc/hostname", "/etc/resolv.conf",
        "/etc/passwd", "/etc/group", "/etc/shadow",
        "/etc/hostname", "/.dockerenv", "/dev/shm", "/dev/mqueue",
    )
    for p in parts:
        if p.fstype in PSEUDO:
            continue
        path = p.mountpoint
        if path in FORBIDDEN_EXACT:
            continue
        if any(path.startswith(pre) for pre in FORBIDDEN_PREFIXES):
            continue
        if p.device in seen:
            continue
        try:
            u = psutil.disk_usage(p.mountpoint)
        except Exception:
            continue
        # Skip absurdly large "disks" that are actually host rootfs shares
        # (unless explicitly /)
        if path != "/" and u.total > (500 * (1 << 30)):
            continue
        seen.add(p.device)
        path = p.mountpoint
        role = ("root" if path == "/"
                else "data" if (path == "/data"
                                or path.startswith("/data/")
                                or path == "/data-nvme"
                                or path.startswith("/data-nvme/"))
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

    # --- Memory limit resolution ---
    # Priority: env override > cgroup (if sane) > HF default
    MEM_HOST_THRESHOLD = 64 * (1 << 30)  # 64 GB: anything above is host
    mem_total = None
    mem_src = None

    env_mem_gb = os.getenv("SUNNYWARE_CONTAINER_MEM_GB")
    if env_mem_gb:
        try:
            gb = int(env_mem_gb)
            if gb > 0:
                mem_total = gb * (1 << 30)
                mem_src = "env"
        except Exception:
            pass

    if mem_total is None:
        cg_mem, _ = _read_cgroup_mem()
        if cg_mem is not None and cg_mem <= MEM_HOST_THRESHOLD:
            mem_total = cg_mem
            mem_src = "cgroup"
        else:
            # cgroup missing OR looks like host RAM -> use HF default 16 GB
            mem_total = 16 * (1 << 30)
            mem_src = "default"

    # --- CPU limit resolution ---
    # Priority: env override > cgroup (if sane) > HF default
    CPU_HOST_THRESHOLD = 8.0  # vCPU: above this is probably host
    cpu_count = None
    cpu_src = None

    env_vcpu = os.getenv("SUNNYWARE_CONTAINER_VCPU")
    if env_vcpu:
        try:
            v = float(env_vcpu)
            if v > 0:
                cpu_count = v
                cpu_src = "env"
        except Exception:
            pass

    if cpu_count is None:
        cg_cpu, _ = _read_cgroup_cpu_count()
        if cg_cpu is not None and cg_cpu <= CPU_HOST_THRESHOLD:
            cpu_count = cg_cpu
            cpu_src = "cgroup"
        else:
            # cgroup missing OR looks like host CPU -> use HF default 2
            cpu_count = 2.0
            cpu_src = "default"

    hide_warn = (os.getenv("SUNNYWARE_LIMITS_HIDE_WARNING", "0")
                 in ("1", "true", "yes", "on"))
    return {
        "cpu_count": round(cpu_count, 2),
        "cpu_source": cpu_src,
        "mem_total_bytes": int(mem_total),
        "mem_source": mem_src,
        "hide_warning": hide_warn,
    }


def sample_once() -> None:
    """Take one sample, append to rolling buffer. Called by background task."""
    global _LAST_CPU_PCT
    import psutil
    try:
        pct = psutil.cpu_percent(interval=None)
    except Exception:
        pct = 0.0
    # Try cgroup memory.current first (v2), then process tree RSS.
    # Never trust psutil.virtual_memory().used in a container - it
    # reports HOST usage, not container usage.
    mem_used = None
    try:
        with open("/sys/fs/cgroup/memory.current") as f:
            mem_used = int(f.read().strip())
    except Exception:
        pass
    if mem_used is None:
        mem_used = _process_tree_mem()
    if mem_used is None:
        try:
            mem_used = int(psutil.virtual_memory().used)
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
    mem_total = lim["mem_total_bytes"]
    # Use the most recent buffer sample (cgroup or process tree based)
    mem_used = 0
    if _BUFFER:
        mem_used = int(_BUFFER[-1].get("mem_used_bytes") or 0)
    if mem_used <= 0:
        mem_used = _process_tree_mem() or 0
    # Clamp in case host-reported cgroup.current > container total
    if mem_total > 0 and mem_used > mem_total:
        mem_used = mem_total
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
