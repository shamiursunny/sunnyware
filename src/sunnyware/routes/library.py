# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Library endpoints: sync files across devices."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from .. import state as app_state
from .. import tenant as tenant_ctx

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

