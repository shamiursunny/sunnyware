# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""SQL sandbox (Part 84).

Creates isolated Postgres schemas (sb_<name>) so the agent can run
ad-hoc SQL without touching main tables (sessions/events/etc).

Safety:
  - search_path forced to the sandbox schema
  - blocked keywords: DROP SCHEMA/DATABASE, ALTER SYSTEM, CREATE EXTENSION
  - blocked identifiers: public., sessions, events, tool_invocations,
    kpi_watches, kpi_watch_events, dynamic_schedules, webhook_*,
    email_send_log, metrics, sql_sandboxes
  - row cap 5000, statement_timeout 10s
"""
import csv
import re
from pathlib import Path
from . import state as app_state

_SANDBOX_PREFIX = "sb_"
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
_MAX_ROWS_RETURNED = 5000
_STATEMENT_TIMEOUT_MS = 10000

_BLOCKED_KEYWORDS = [
    r"\bdrop\s+schema\b",
    r"\bdrop\s+database\b",
    r"\balter\s+system\b",
    r"\bcreate\s+extension\b",
    r"\bdrop\s+extension\b",
    r"\bpg_read_file\b",
    r"\bpg_ls_dir\b",
    r"\bcopy\s+.*\bfrom\s+program\b",
    r"\bpg_sleep\b",
]
_BLOCKED_IDENTS = [
    "public.", "public ", " public", "pg_catalog.", "information_schema.",
    "sessions", "events", "tool_invocations", "kpi_watches",
    "kpi_watch_events", "dynamic_schedules", "webhook_endpoints",
    "webhook_events", "email_send_log", "sql_sandboxes",
    "metrics", "scheduled_jobs",
]


def _validate_name(name: str):
    name = (name or "").strip().lower()
    if not _NAME_RE.match(name):
        return None, "name must match [a-z][a-z0-9_]{0,40}"
    return name, None


def _check_sql(sql: str):
    s = sql or ""
    low = s.lower()
    for pat in _BLOCKED_KEYWORDS:
        if re.search(pat, low):
            return "blocked keyword: " + pat
    for ident in _BLOCKED_IDENTS:
        # word-boundary-ish; allow pg_temp
        if ident in low:
            return "blocked identifier: " + ident
    return None


def _workspace_root() -> Path:
    import os
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


async def create(name: str, description: str = "") -> dict:
    name, err = _validate_name(name)
    if err:
        return {"error": err}
    schema = _SANDBOX_PREFIX + name
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            await conn.execute("CREATE SCHEMA IF NOT EXISTS " + schema)
            await conn.execute(
                """INSERT INTO sql_sandboxes (name, schema_name, description)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description""",
                name, schema, (description or "")[:300])
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}
    return {"ok": True, "name": name, "schema": schema}


async def execute(name: str, sql: str, params=None) -> dict:
    name, err = _validate_name(name)
    if err:
        return {"error": err}
    err = _check_sql(sql)
    if err:
        return {"error": err}
    schema = _SANDBOX_PREFIX + name
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}

    # params: list of values for $1..$n (optional)
    args = []
    if isinstance(params, list):
        args = params[:20]

    try:
        async with pool.acquire() as conn:
            # Ensure schema exists
            row = await conn.fetchrow(
                "SELECT 1 FROM sql_sandboxes WHERE name = $1", name)
            if row is None:
                return {"error": "sandbox not found: " + name}

            s = sql.strip().rstrip(";")
            low = s.lower()
            is_query = low.startswith("select") or low.startswith("with") or low.startswith("show") or low.startswith("explain")
            has_returning = " returning " in low

            # Part 84-fix: wrap in explicit transaction so SET LOCAL sticks.
            # (SET LOCAL outside a transaction is discarded by asyncpg.)
            async with conn.transaction():
                await conn.execute("SET LOCAL search_path TO " + schema + ", pg_temp")
                await conn.execute(
                    "SET LOCAL statement_timeout = " + str(_STATEMENT_TIMEOUT_MS))
                # Verify search_path took effect
                cur_path = await conn.fetchval("SHOW search_path")
                if schema not in str(cur_path):
                    return {"error": "search_path set failed: " + str(cur_path)}

                if is_query or has_returning:
                    rows = await conn.fetch(s, *args)
                    out_rows = [dict(r) for r in rows[:_MAX_ROWS_RETURNED]]
                    for r in out_rows:
                        for k, v in list(r.items()):
                            if hasattr(v, "isoformat"):
                                r[k] = v.isoformat()
                            elif isinstance(v, (bytes, memoryview)):
                                r[k] = "<" + str(len(v)) + " bytes>"
                    truncated = len(rows) > _MAX_ROWS_RETURNED
                else:
                    out_rows = []
                    truncated = False
                    result = await conn.execute(s, *args)

            # Outside transaction: update accounting
            try:
                await conn.execute(
                    "UPDATE sql_sandboxes SET last_used_at = NOW(), query_count = query_count + 1 WHERE name = $1",
                    name)
            except Exception:
                pass

            if is_query or has_returning:
                return {
                    "ok": True, "sandbox": name, "schema": schema,
                    "row_count": len(out_rows),
                    "truncated": truncated,
                    "columns": list(out_rows[0].keys()) if out_rows else [],
                    "rows": out_rows,
                }
            else:
                return {"ok": True, "sandbox": name, "result": str(result)}
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:250]}


async def list_all() -> dict:
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            sbs = await conn.fetch(
                """SELECT name, schema_name, description, created_at,
                          last_used_at, query_count
                   FROM sql_sandboxes ORDER BY created_at DESC""")
            out = []
            for sb in sbs:
                schema = sb["schema_name"]
                tables = []
                try:
                    trows = await conn.fetch(
                        """SELECT table_name FROM information_schema.tables
                           WHERE table_schema = $1 ORDER BY table_name""",
                        schema)
                    for t in trows:
                        tname = t["table_name"]
                        try:
                            cnt = await conn.fetchval(
                                'SELECT count(*) FROM "' + schema + '"."' + tname + '"'
                            )
                        except Exception:
                            cnt = None
                        tables.append({"name": tname, "rows": int(cnt) if cnt is not None else None})
                except Exception:
                    pass
                out.append({
                    "name": sb["name"],
                    "schema": schema,
                    "description": sb["description"] or "",
                    "created_at": sb["created_at"].isoformat() if sb["created_at"] else None,
                    "last_used_at": sb["last_used_at"].isoformat() if sb["last_used_at"] else None,
                    "query_count": int(sb["query_count"]),
                    "tables": tables,
                })
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}
    return {"count": len(out), "sandboxes": out}


async def load_csv(name: str, file: str, table: str) -> dict:
    name, err = _validate_name(name)
    if err:
        return {"error": err}
    table = (table or "").strip().lower()
    if not _NAME_RE.match(table):
        return {"error": "table must match [a-z][a-z0-9_]{0,40}"}
    schema = _SANDBOX_PREFIX + name

    root = _workspace_root()
    candidate = (root / file).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return {"error": "file must live inside workspace"}
    if not candidate.exists():
        return {"error": "file not found: " + file}
    if candidate.suffix.lower() not in (".csv", ".tsv"):
        return {"error": "only .csv or .tsv files"}

    delim = "\t" if candidate.suffix.lower() == ".tsv" else ","
    try:
        with candidate.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh, delimiter=delim)
            headers = next(reader)
            rows = list(reader)
    except Exception as e:
        return {"error": "csv read failed: " + type(e).__name__ + ": " + str(e)[:150]}

    if not headers or not rows:
        return {"error": "empty csv"}
    # Sanitize column names
    clean_headers = []
    seen = set()
    for h in headers:
        ch = re.sub(r"[^a-z0-9_]", "_", str(h).strip().lower())[:60] or "col"
        while ch in seen:
            ch += "_"
        seen.add(ch)
        clean_headers.append(ch)

    # All TEXT to keep it simple (agent can CAST in SQL)
    cols_sql = ", ".join('"' + c + '" TEXT' for c in clean_headers)

    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}

    try:
        async with pool.acquire() as conn:
            await conn.execute("CREATE SCHEMA IF NOT EXISTS " + schema)
            await conn.execute('DROP TABLE IF EXISTS "' + schema + '"."' + table + '"')
            await conn.execute('CREATE TABLE "' + schema + '"."' + table + '" (' + cols_sql + ')')
            placeholders = ", ".join("$" + str(i + 1) for i in range(len(clean_headers)))
            insert_sql = ('INSERT INTO "' + schema + '"."' + table + '" VALUES (' + placeholders + ')')
            # Insert in batches
            batch = []
            for r in rows:
                # pad/truncate to header count
                if len(r) < len(clean_headers):
                    r = r + [""] * (len(clean_headers) - len(r))
                elif len(r) > len(clean_headers):
                    r = r[:len(clean_headers)]
                batch.append(tuple(r))
                if len(batch) >= 500:
                    await conn.executemany(insert_sql, batch)
                    batch = []
            if batch:
                await conn.executemany(insert_sql, batch)
            await conn.execute(
                "UPDATE sql_sandboxes SET last_used_at = NOW() WHERE name = $1",
                name)
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}

    return {
        "ok": True, "sandbox": name, "table": table,
        "rows_loaded": len(rows),
        "columns": clean_headers,
    }


async def drop(name: str) -> dict:
    name, err = _validate_name(name)
    if err:
        return {"error": err}
    schema = _SANDBOX_PREFIX + name
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        async with pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS " + schema + " CASCADE")
            await conn.execute("DELETE FROM sql_sandboxes WHERE name = $1", name)
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:200]}
    return {"ok": True, "name": name, "dropped_schema": schema}
