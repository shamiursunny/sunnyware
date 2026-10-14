# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 106: persistent image attachment store.

Saves base64-encoded images returned by tools (image_generate,
chart_from_data, browser_screenshot, etc.) to /data/attachments/ so
they survive browser refresh, session reload, and Space restarts.

URL shape: /api/attachments/<id>.<ext>
"""
import base64
import os
import secrets
from pathlib import Path
from typing import Optional, Tuple

_ATTACH_ROOT: Optional[Path] = None
_ATTACH_SOURCE: Optional[str] = None
_ATTACH_CACHE: Optional[Path] = None

_EXT_WHITELIST = {"png", "jpg", "jpeg", "webp", "gif"}


def _probe_writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    probe = d / ".sunnyware_attach_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _resolve_attach_root() -> "tuple[Path, str]":
    env_dir = (os.getenv("SUNNYWARE_DATA_DIR") or "").strip()
    if env_dir:
        d = Path(env_dir) / "attachments"
        if _probe_writable(d):
            return d, "env:SUNNYWARE_DATA_DIR"
    if os.name == "posix":
        hf_dir = Path("/data/attachments")
        if _probe_writable(hf_dir):
            return hf_dir, "hf:/data/attachments"
    local = Path("data/attachments")
    _probe_writable(local)
    return local, "local:./data/attachments"


def root() -> Path:
    global _ATTACH_ROOT, _ATTACH_SOURCE, _ATTACH_CACHE
    if _ATTACH_ROOT is not None:
        return _ATTACH_ROOT
    path, source = _resolve_attach_root()
    _ATTACH_ROOT = path
    _ATTACH_SOURCE = source
    _ATTACH_CACHE = path
    try:
        print(f"[attachments] storage source={source} path={path}",
              flush=True)
    except Exception:
        pass
    return _ATTACH_ROOT


def path_source() -> str:
    root()
    return _ATTACH_SOURCE or "unknown"


def save_base64(b64_data: str, ext: str = "png") -> Optional[dict]:
    """Save a base64-encoded image. Returns {id, ext, url, bytes} or None."""
    if not isinstance(b64_data, str) or not b64_data:
        return None
    e = (ext or "png").lower().lstrip(".").strip()
    if e == "jpeg":
        e = "jpg"
    if e not in _EXT_WHITELIST:
        e = "png"
    try:
        raw = base64.b64decode(b64_data, validate=False)
    except Exception:
        return None
    if not raw or len(raw) > 8 * 1024 * 1024:
        return None
    att_id = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
    p = root() / f"{att_id}.{e}"
    try:
        p.write_bytes(raw)
    except Exception as exc:
        print(f"[attachments] save failed: {type(exc).__name__}: {exc}",
              flush=True)
        return None
    return {
        "id": att_id,
        "ext": e,
        "url": f"/api/attachments/{att_id}.{e}",
        "bytes": len(raw),
    }


def resolve_path(att_id: str, ext: str) -> Optional[Path]:
    """Resolve an attachment id+ext to a path (guards traversal)."""
    if not att_id or not ext:
        return None
    e = ext.lower().lstrip(".").strip()
    if e == "jpeg":
        e = "jpg"
    if e not in _EXT_WHITELIST:
        return None
    # Reject any id containing path separators
    if any(ch in att_id for ch in ("/", "\\", "..")):
        return None
    p = root() / f"{att_id}.{e}"
    if not p.is_file():
        return None
    return p


def stats() -> dict:
    r = root()
    try:
        files = list(r.glob("*.*"))
    except Exception:
        files = []
    total_bytes = 0
    for f in files:
        try:
            total_bytes += f.stat().st_size
        except Exception:
            pass
    return {
        "path": str(r),
        "path_source": path_source(),
        "file_count": len(files),
        "total_bytes": total_bytes,
    }
