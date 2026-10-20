# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 223: Backup & Restore routes."""

import io
import json
import os
import time
import zipfile
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(tags=["backup"])


def _admin_only(req: Request):
    from .. import auth as _auth
    key = req.headers.get("x-api-key") or ""
    if not key:
        authz = req.headers.get("authorization") or ""
        if authz.lower().startswith("bearer "):
            key = authz[7:].strip()
    if not _auth.auth_enabled():
        return None
    if not key or not _auth.is_valid_key(key):
        return JSONResponse({"error": "auth_required"}, status_code=401)
    if not _auth.has_role(_auth.role_for_key(key), "admin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return None


def _data_dir() -> Path:
    data = Path("/data")
    if data.exists() and os.access(str(data), os.W_OK):
        return data
    return Path("data")


@router.get("/api/backup/list")
async def list_files(req: Request):
    d = _admin_only(req)
    if d: return d
    data_dir = _data_dir()
    files = []
    for f in sorted(data_dir.glob("*.json")):
        try:
            st = f.stat()
            files.append({
                "name": f.name,
                "size": st.st_size,
                "modified": st.st_mtime,
            })
        except Exception:
            pass
    return {"count": len(files), "files": files}


@router.get("/api/backup/export")
async def export_backup(req: Request):
    d = _admin_only(req)
    if d: return d
    data_dir = _data_dir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(data_dir.glob("*.json")):
            zf.write(f, arcname=f.name)
    buf.seek(0)
    ts = time.strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="sunnyware_backup_{ts}.zip"',
            "Content-Length": str(len(buf.getvalue())),
        },
    )


@router.post("/api/backup/validate")
async def validate_backup(req: Request):
    """Parse a ZIP and return its contents. Does NOT change any data."""
    d = _admin_only(req)
    if d: return d
    try:
        form = await req.form()
    except Exception as e:
        return JSONResponse({"error": f"Invalid form data: {e}"}, status_code=400)
    file = form.get("file")
    if not file:
        return JSONResponse({"error": "No file provided"}, status_code=400)
    content = await file.read()
    if not content:
        return JSONResponse({"error": "Empty file"}, status_code=400)
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            items = []
            total = 0
            for info in zf.infolist():
                # Skip directories
                if info.filename.endswith("/"):
                    continue
                items.append({
                    "name": info.filename,
                    "size": info.file_size,
                    "is_json": info.filename.endswith(".json"),
                    "is_safe": "/" not in info.filename and "\\" not in info.filename and ".." not in info.filename,
                })
                total += info.file_size
            return {
                "ok": True,
                "count": len(items),
                "total_bytes": total,
                "files": items,
            }
    except zipfile.BadZipFile:
        return JSONResponse({"error": "Not a valid ZIP file"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Could not parse ZIP: {e}"}, status_code=400)


@router.post("/api/backup/restore")
async def restore_backup(req: Request):
    """Restore JSON files from a backup ZIP. Only .json files at the root are extracted."""
    d = _admin_only(req)
    if d: return d
    try:
        form = await req.form()
    except Exception as e:
        return JSONResponse({"error": f"Invalid form data: {e}"}, status_code=400)
    file = form.get("file")
    confirm = form.get("confirm", "")
    if confirm != "RESTORE":
        return JSONResponse({"error": "Must type RESTORE to confirm"}, status_code=400)
    if not file:
        return JSONResponse({"error": "No file provided"}, status_code=400)
    content = await file.read()
    if not content:
        return JSONResponse({"error": "Empty file"}, status_code=400)

    data_dir = _data_dir()

    # 1. Parse ZIP and identify safe .json files
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            safe_json = []
            for name in zf.namelist():
                # Skip directories
                if name.endswith("/"):
                    continue
                # Only .json
                if not name.endswith(".json"):
                    continue
                # Prevent path traversal
                if "/" in name or "\\" in name or ".." in name:
                    continue
                # Verify it's valid JSON
                try:
                    raw = zf.read(name)
                    json.loads(raw.decode("utf-8"))
                except Exception:
                    continue  # Skip invalid JSON files
                safe_json.append(name)
    except zipfile.BadZipFile:
        return JSONResponse({"error": "Not a valid ZIP file"}, status_code=400)

    if not safe_json:
        return JSONResponse({"error": "No valid .json files found in ZIP"}, status_code=400)

    # 2. Snapshot current state before restoring
    snapshot_name = ""
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"backup_pre_restore_{ts}.zip"
        snapshot_path = data_dir / snapshot_name
        with zipfile.ZipFile(snapshot_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in data_dir.glob("*.json"):
                zf.write(f, arcname=f.name)
    except Exception:
        pass  # Don't fail the restore if snapshot fails

    # 3. Restore files
    restored = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in safe_json:
                target = data_dir / name
                with zf.open(name) as src:
                    data = src.read()
                target.write_bytes(data)
                restored.append(name)
    except Exception as e:
        return JSONResponse({"error": f"Restore failed: {e}"}, status_code=500)

    return {
        "ok": True,
        "count": len(restored),
        "restored": restored,
        "snapshot": snapshot_name,
    }
