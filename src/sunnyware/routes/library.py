# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Library endpoints: sync files across devices."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import state as app_state
from .. import tenant as tenant_ctx
from pathlib import Path

router = APIRouter()

def _owner() -> str:
    raw = tenant_ctx.get_key()
    if not raw: return ""
    if "." in raw and len(raw) > 20:
        try:
            from .auth import verify_jwt
            email = verify_jwt(raw)
            if email: return f"user:{email}"
        except Exception: pass
    return raw

async def _ensure_table():
    pool = app_state.get_pool()
    if not pool: return
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS library_files (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                owner_key TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT,
                size INT,
                kind TEXT,
                content TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_library_owner ON library_files(owner_key);
        """)

@router.get("/api/library/files")
async def list_files():
    pool = app_state.get_pool()
    if not pool: return {"files": []}
    await _ensure_table()
    owner = _owner()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, type, size, kind, content, created_at FROM library_files WHERE owner_key = $1 ORDER BY created_at DESC", owner)
        out = []
        for r in rows:
            d = dict(r)
            d["id"] = str(d["id"])
            d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return {"files": out}

@router.post("/api/library/files")
async def save_file(req: Request):
    pool = app_state.get_pool()
    if not pool:
        # DB unavailable — accept the upload but return a warning instead of failing
        return JSONResponse({"ok": True, "db": False, "warning": "No database configured — file saved locally only"})
    await _ensure_table()
    owner = _owner()
    body = await req.json()
    content = body.get("content", "")
    size = body.get("size") or 0

    # Derive size from content when missing (e.g. text files uploaded before sync fix)
    if not size and content:
        if isinstance(content, str):
            if content.startswith('data:'):
                try:
                    import base64 as _b64
                    b64_part = content.split(',', 1)[1] if ',' in content else ''
                    size = len(_b64.b64decode(b64_part))
                except Exception:
                    size = len(content)
            else:
                size = len(content.encode('utf-8'))

    # Part 258: Prevent DoS via massive base64 payloads (max 5MB)
    if len(content) > 5 * 1024 * 1024:
        return JSONResponse(
            {"error": "File too large", "detail": "Max size is 5MB"}, 
            status_code=413
        )

    # Part 259: Limit to 100 files per user to prevent storage abuse
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM library_files WHERE owner_key = $1", owner)
        if count >= 100:
            return JSONResponse(
                {"error": "File limit reached", "detail": "Max 100 files per user. Delete some files first."},
                status_code=429,
            )

        row = await conn.fetchrow("""
            INSERT INTO library_files (owner_key, name, type, size, kind, content)
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING id, created_at
        """, owner, body.get("name", "Untitled"), body.get("type", "file"), size, body.get("kind", "upload"), content)
        return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}

@router.delete("/api/library/files/{file_id}")
async def delete_file(file_id: str):
    pool = app_state.get_pool()
    if not pool: return {"deleted": False}
    await _ensure_table()
    owner = _owner()
    # Part 258: validate UUID before casting to prevent 500 errors
    import uuid
    try:
        uuid.UUID(file_id)
    except ValueError:
        return JSONResponse({"error": "Invalid file ID"}, status_code=400)

    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM library_files WHERE id = $1::uuid AND owner_key = $2", file_id, owner)
        return {"deleted": res.startswith("DELETE 1")}

from datetime import datetime

@router.get("/api/workspace/files")
async def list_workspace_files():
    """List files in the agent workspace directory."""
    from .. import paths
    ws = paths.workspace()
    if not ws.exists():
        return {"files": []}
    out = []
    for f in ws.iterdir():
        if not f.is_file():
            continue
        stat = f.stat()
        out.append({
            "name": f.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "type": f.suffix.lstrip(".").lower() or "file",
        })
    out.sort(key=lambda x: x["modified"], reverse=True)
    return {"files": out}


@router.get("/api/sandbox/download-zip")
async def download_sandbox_zip():
    """Package all sandbox files into a single ZIP and return it."""
    from fastapi.responses import Response
    from .. import paths
    import io, zipfile
    sb = paths.sandbox()
    if not sb.exists():
        return {"error": "sandbox does not exist"}
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sb.iterdir():
            if f.is_file():
                zf.write(f, arcname=f.name)
                count += 1
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="sandbox-{count}-files.zip"'},
    )


@router.get("/api/workspace/download-zip")
async def download_workspace_zip():
    """Package all workspace files into a single ZIP."""
    from fastapi.responses import Response
    from .. import paths
    import io, zipfile
    ws = paths.workspace()
    if not ws.exists():
        return {"error": "workspace does not exist"}
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in ws.iterdir():
            if f.is_file():
                zf.write(f, arcname=f.name)
                count += 1
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="workspace-{count}-files.zip"'},
    )


@router.get("/api/library/download-zip")
async def download_uploaded_zip():
    """Package all uploaded files (from DB) into a single ZIP."""
    from fastapi.responses import Response
    import io, zipfile, base64
    pool = app_state.get_pool()
    
    # If no DB, try local fallback directories
    if not pool:
        from .. import paths
        for d in [paths.data_root() / "library", paths.data_root() / "uploads"]:
            if d.exists() and any(d.iterdir()):
                buf = io.BytesIO()
                count = 0
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for f in d.iterdir():
                        if f.is_file():
                            zf.write(f, arcname=f.name)
                            count += 1
                buf.seek(0)
                return Response(
                    content=buf.read(),
                    media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="uploaded-{count}-files.zip"'},
                )
        return {"error": "no database and no local uploaded files found"}
    
    try:
        await _ensure_table()
        owner = _owner()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, type, content FROM library_files WHERE owner_key = $1 ORDER BY created_at DESC",
                owner,
            )
        if not rows:
            return {"error": "no uploaded files in database"}
            
        buf = io.BytesIO()
        used_names = set()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in rows:
                name = r["name"] or "untitled"
                if name in used_names:
                    stem, dot, ext = name.rpartition(".")
                    i = 2
                    while f"{stem}_{i}.{ext}" in used_names:
                        i += 1
                    name = f"{stem}_{i}.{ext}"
                used_names.add(name)
                content = r["content"] or ""
                ftype = (r["type"] or "").lower()
                try:
                    if ftype == "image" or content.startswith("data:"):
                        if content.startswith("data:"):
                            b64 = content.split(",", 1)[-1]
                        else:
                            b64 = content
                        zf.writestr(name, base64.b64decode(b64))
                    else:
                        zf.writestr(name, content)
                except Exception:
                    zf.writestr(name, content)
        buf.seek(0)
        return Response(
            content=buf.read(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="uploaded-{len(rows)}-files.zip"'},
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": f"ZIP generation failed: {str(e)}"}

@router.get("/api/sandbox/file/{filename}")
async def get_sandbox_file(filename: str):
    """Read a single sandbox file's content (text or base64 for images)."""
    from .. import paths
    import base64
    name = Path(filename).name
    target = paths.sandbox() / name
    if not target.exists() or not target.is_file():
        return {"error": "file not found"}
    ext = target.suffix.lower()
    try:
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"):
            data = base64.b64encode(target.read_bytes()).decode()
            mime = "image/svg+xml" if ext == ".svg" else f"image/{ext[1:]}"
            return {"ok": True, "name": name, "type": "image", "content": data,
                    "mime": mime, "size": target.stat().st_size}
        if ext in (".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".zip", ".gz", ".tar"):
            return {"ok": True, "name": name, "type": "binary", "size": target.stat().st_size,
                    "content": f"Preview not available for {ext} files. Click Download."}
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > 500_000:
            content = content[:500_000] + "\n\n... (truncated)"
        return {"ok": True, "name": name, "type": "text", "content": content,
                "size": target.stat().st_size}
    except Exception as e:
        return {"error": f"read failed: {type(e).__name__}: {e}"}


@router.get("/api/workspace/file/{filename}/xlsx")
async def get_workspace_xlsx(filename: str):
    """Parse an xlsx file in the workspace and return sheets as JSON."""
    from pathlib import Path as _Path
    try:
        from .. import paths
        name = _Path(filename).name
        target = paths.workspace() / name
        if not target.exists():
            return {"error": f"file not found: {name}"}
        if target.suffix.lower() not in (".xlsx", ".xls"):
            return {"error": "not an xlsx file"}
        try:
            import openpyxl
        except ImportError:
            return {"error": "openpyxl not installed"}
        wb = openpyxl.load_workbook(str(target), data_only=True, read_only=True)
        sheets = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_iter = ws.iter_rows(values_only=True)
            try:
                headers_row = next(rows_iter, None)
            except StopIteration:
                headers_row = None
            if not headers_row:
                sheets[sheet_name] = {"headers": [], "rows": []}
                continue
            headers = [str(h) if h is not None else f"col{i+1}" for i, h in enumerate(headers_row)]
            rows = []
            for r in rows_iter:
                if all(c is None for c in r):
                    continue
                row_dict = {}
                for i, h in enumerate(headers):
                    row_dict[h] = r[i] if i < len(r) else None
                rows.append(row_dict)
            sheets[sheet_name] = {"headers": headers, "rows": rows[:2000]}
        wb.close()
        return {"ok": True, "name": name, "sheets": sheets}
    except Exception as e:
        return {"error": f"xlsx parse failed: {type(e).__name__}: {e}"}




def _office_preview_dispatch(kind: str, filename: str):
    """Shared dispatcher for office-preview endpoints."""
    from pathlib import Path as _Path
    from .. import paths
    from .. import office_preview
    base = paths.workspace() if kind == "workspace" else paths.sandbox()
    name = _Path(filename).name
    target = base / name
    if not target.exists():
        return {"error": f"file not found: {name}"}
    ext = target.suffix.lower()
    if ext == ".doc":  return office_preview.parse_doc(target)
    if ext == ".docx": return office_preview.parse_docx(target)
    if ext == ".ppt":  return office_preview.parse_ppt(target)
    if ext == ".pptx": return office_preview.parse_pptx(target)
    if ext == ".xls":  return office_preview.parse_xls(target)
    if ext == ".twb":  return office_preview.parse_twb(target)
    if ext == ".twbx": return office_preview.parse_twbx(target)
    if ext == ".pbix": return office_preview.parse_pbix(target)
    return {"error": f"unsupported preview format: {ext}"}


@router.get("/api/workspace/file/{filename}/office-preview")
async def get_workspace_office_preview(filename: str):
    try: return _office_preview_dispatch("workspace", filename)
    except Exception as e: return {"error": f"dispatch failed: {type(e).__name__}: {e}"}


@router.get("/api/sandbox/file/{filename}/office-preview")
async def get_sandbox_office_preview(filename: str):
    try: return _office_preview_dispatch("sandbox", filename)
    except Exception as e: return {"error": f"dispatch failed: {type(e).__name__}: {e}"}

@router.get("/api/workspace/file/{filename}")
async def get_workspace_file(filename: str):
    """Read a single workspace file's content (text / image / pdf / base64)."""
    from pathlib import Path as _Path
    import base64
    try:
        from .. import paths
        name = _Path(filename).name
        target = paths.workspace() / name
        if not target.exists() or not target.is_file():
            return {"error": f"file not found: {name}"}
        ext = target.suffix.lower()
        size = target.stat().st_size
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"):
            data = base64.b64encode(target.read_bytes()).decode()
            mime = "image/svg+xml" if ext == ".svg" else f"image/{ext[1:]}"
            return {"ok": True, "name": name, "type": "image", "content": data, "mime": mime, "size": size}
        if ext == ".pdf":
            data = base64.b64encode(target.read_bytes()).decode()
            return {"ok": True, "name": name, "type": "pdf", "content": data, "mime": "application/pdf", "size": size}
        if ext in (".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt", ".zip", ".gz", ".tar"):
            return {"ok": True, "name": name, "type": "binary", "size": size,
                    "content": f"Preview not available for {ext} files. Click Download."}
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > 500_000:
            content = content[:500_000] + "\n\n... (truncated)"
        return {"ok": True, "name": name, "type": "text", "content": content, "size": size}
    except Exception as e:
        return {"error": f"read failed: {type(e).__name__}: {e}"}


@router.get("/api/sandbox/file/{filename}/xlsx")
async def get_sandbox_xlsx(filename: str):
    """Parse an xlsx file in the sandbox and return sheets as JSON (mirrors excel_read output)."""
    from pathlib import Path as _Path
    try:
        from .. import paths
        name = _Path(filename).name
        target = paths.sandbox() / name
        if not target.exists():
            return {"error": f"file not found: {name}"}
        if target.suffix.lower() not in (".xlsx", ".xls"):
            return {"error": "not an xlsx file"}
        try:
            import openpyxl
        except ImportError:
            return {"error": "openpyxl not installed"}
        wb = openpyxl.load_workbook(str(target), read_only=True, data_only=True)
        sheets = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_iter = ws.iter_rows(values_only=True)
            try:
                headers_row = next(rows_iter, None)
            except StopIteration:
                headers_row = None
            if not headers_row:
                sheets[sheet_name] = {"headers": [], "rows": []}
                continue
            headers = [str(h) if h is not None else f"col{i+1}" for i, h in enumerate(headers_row)]
            rows = []
            for r in rows_iter:
                if all(c is None for c in r):
                    continue
                row_dict = {}
                for i, h in enumerate(headers):
                    row_dict[h] = r[i] if i < len(r) else None
                rows.append(row_dict)
            sheets[sheet_name] = {"headers": headers, "rows": rows[:2000]}
        wb.close()
        return {"ok": True, "name": name, "sheets": sheets}
    except Exception as e:
        return {"error": f"xlsx parse failed: {type(e).__name__}: {e}"}


@router.delete("/api/sandbox/file/{filename}")
async def delete_sandbox_file(filename: str):
    """Delete a single file from the sandbox."""
    from .. import paths
    name = Path(filename).name
    target = paths.sandbox() / name
    if not target.exists():
        return {"ok": False, "error": "file not found"}
    try:
        target.unlink()
        return {"ok": True, "deleted": name}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/sandbox/clear")
async def clear_sandbox():
    """Delete all files in the sandbox."""
    from .. import paths
    sb = paths.sandbox()
    if not sb.exists():
        return {"ok": True, "deleted": 0}
    count = 0
    errors = []
    for f in sb.iterdir():
        if f.is_file():
            try:
                f.unlink()
                count += 1
            except Exception as e:
                errors.append(f"{f.name}: {e}")
    return {"ok": True, "deleted": count, "errors": errors}

@router.get("/api/sandbox/files")
async def list_sandbox_files():
    """List files in the agent sandbox directory."""
    from .. import paths
    sb = paths.sandbox()
    if not sb.exists():
        return {"files": []}
    out = []
    for f in sb.iterdir():
        if not f.is_file():
            continue
        stat = f.stat()
        out.append({
            "name": f.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "type": f.suffix.lstrip(".").lower() or "file",
        })
    out.sort(key=lambda x: x["modified"], reverse=True)
    return {"files": out}

