# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Application state — asyncpg pool OR local DuckDB fallback.

Auto-detects:
- NEON_DATABASE_URL set   → use asyncpg (existing behavior)
- NEON_DATABASE_URL unset → use local DuckDB at SUNNYWARE_DATA_DIR/sunnyware.duckdb
- SUNNYWARE_USE_LOCAL_DB=1 → force local DuckDB even if Neon is configured

Both pool types expose the same interface (pool.acquire() context manager with
.fetch(), .fetchrow(), .fetchval(), .execute(), .executemany()).

DuckDB connection translates Postgres SQL → DuckDB syntax on the fly.
"""

import asyncio
import os
import re
import sys
import threading
from pathlib import Path
from typing import Optional


if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass


try:
    import asyncpg
    _HAS_ASYNCPG = True
except ImportError:
    asyncpg = None
    _HAS_ASYNCPG = False

try:
    import duckdb
    _HAS_DUCKDB = True
except ImportError:
    duckdb = None
    _HAS_DUCKDB = False


_pool = None
_last_error: Optional[str] = None
_pool_kind: Optional[str] = None  # "postgres" or "duckdb"


# ─── SQL Translation (Postgres → DuckDB) ─────────────────────────────
def _translate_sql(sql: str) -> str:
    """Translate Postgres-specific syntax to DuckDB equivalent."""
    # $1, $2, ... → ?
    sql = re.sub(r"\$\d+", "?", sql)
    # make_interval(days => N) → (CAST(N AS INTEGER) * INTERVAL 1 DAY)
    sql = re.sub(
        r"make_interval\s*\(\s*days\s*=>\s*([^)]+)\)",
        r"(CAST(\1 AS INTEGER) * INTERVAL 1 DAY)",
        sql,
        flags=re.IGNORECASE,
    )
    # SET LOCAL search_path TO x, pg_temp → SET schema = 'x'
    sql = re.sub(
        r"SET\s+(?:LOCAL\s+)?search_path\s+TO\s+([^,\s]+)\s*,\s*pg_temp",
        r"SET schema = '\1'",
        sql,
        flags=re.IGNORECASE,
    )
    # SET search_path TO x → SET schema = 'x'
    sql = re.sub(
        r"SET\s+(?:LOCAL\s+)?search_path\s+TO\s+([^,\s]+)\s*$",
        r"SET schema = '\1'",
        sql,
        flags=re.IGNORECASE,
    )
    # SHOW search_path → current_schema()
    sql = re.sub(
        r"SHOW\s+search_path",
        "SELECT current_schema() AS search_path",
        sql,
        flags=re.IGNORECASE,
    )
    # payload::text → CAST(payload AS VARCHAR) — simpler: keep as-is, DuckDB supports ::
    return sql


def _translate_sql_with_args(sql: str, args: list):
    """Translate $N placeholders AND reorder args to match ? position order."""
    positions = []
    for m in re.finditer(r"\$(\d+)", sql):
        positions.append(int(m.group(1)) - 1)
    sql = re.sub(r"\$\d+", "?", sql)
    sql = re.sub(
        r"make_interval\s*\(\s*days\s*=>\s*([^)]+)\)",
        r"(CAST(\1 AS INTEGER) * INTERVAL 1 DAY)",
        sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"SET\s+(?:LOCAL\s+)?search_path\s+TO\s+([^,\s]+)\s*,\s*pg_temp",
        r"SET schema = '\1'", sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"SET\s+(?:LOCAL\s+)?search_path\s+TO\s+([^,\s]+)\s*$",
        r"SET schema = '\1'", sql, flags=re.IGNORECASE,
    )
    sql = re.sub(r"SHOW\s+search_path", "SELECT current_schema() AS search_path", sql, flags=re.IGNORECASE)
    new_args = [args[i] if i < len(args) else None for i in positions]
    return sql, new_args


def _translate_ddl(stmt: str) -> str:
    """Translate one DDL statement from Postgres to DuckDB."""
    # TIMESTAMPTZ → TIMESTAMP WITH TIME ZONE (native)
    stmt = re.sub(r"\bTIMESTAMPTZ\b", "TIMESTAMP WITH TIME ZONE", stmt, flags=re.IGNORECASE)
    # JSONB → JSON (native)
    stmt = re.sub(r"\bJSONB\b", "JSON", stmt, flags=re.IGNORECASE)
    # '{}'::jsonb → '{}'
    stmt = re.sub(r"'(\{[^']*\})'::jsonb", r"'\1'", stmt, flags=re.IGNORECASE)
    # gen_random_uuid() → uuid()
    stmt = re.sub(r"\bgen_random_uuid\s*\(\s*\)", "uuid()", stmt, flags=re.IGNORECASE)

    # ── Strip FOREIGN KEY constraints (DuckDB limitation) ──
    # Remove: REFERENCES tablename (cols) ON DELETE CASCADE / ON UPDATE CASCADE etc
    stmt = re.sub(
        r"\s+REFERENCES\s+\w+\s*\([^)]*\)(?:\s+ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|SET\s+NULL|SET\s+DEFAULT))?",
        "",
        stmt,
        flags=re.IGNORECASE,
    )
    # Remove: FOREIGN KEY (col) REFERENCES ... (some syntax variations)
    stmt = re.sub(
        r",?\s*FOREIGN\s+KEY\s*\([^)]*\)\s*REFERENCES\s+\w+\s*\([^)]*\)(?:\s+ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|SET\s+NULL|SET\s+DEFAULT))?",
        "",
        stmt,
        flags=re.IGNORECASE,
    )
    # Remove any standalone ON DELETE CASCADE / ON UPDATE CASCADE
    stmt = re.sub(r"\s+ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|SET\s+NULL|SET\s+DEFAULT)", "", stmt, flags=re.IGNORECASE)

    # ── ALTER TABLE limitations in DuckDB ──
    # DuckDB doesn't support: ADD COLUMN with NOT NULL
    # Strip NOT NULL from ADD COLUMN clauses
    if re.search(r"ALTER\s+TABLE\b", stmt, re.IGNORECASE) and re.search(r"ADD\s+COLUMN", stmt, re.IGNORECASE):
        stmt = re.sub(r"\bNOT\s+NULL\b", "", stmt, flags=re.IGNORECASE)

    # DuckDB doesn't support: ALTER COLUMN ... SET NOT NULL
    if re.search(r"ALTER\s+COLUMN\s+\w+\s+SET\s+NOT\s+NULL", stmt, re.IGNORECASE):
        return ""  # skip this statement entirely

    return stmt


def _split_statements(sql: str):
    """Split a .sql file into individual statements (naive but works for migrations)."""
    # Strip line comments
    lines = []
    for line in sql.split("\n"):
        # Remove -- comments outside of strings (simple heuristic)
        if "--" in line:
            # Check if it's inside a string — basic check
            idx = line.find("--")
            pre = line[:idx]
            if pre.count("'") % 2 == 0:  # even number of quotes before --
                line = pre
        lines.append(line)
    sql = "\n".join(lines)
    # Split on semicolons
    parts = []
    current = []
    in_string = False
    for char in sql:
        if char == "'":
            in_string = not in_string
        if char == ";" and not in_string:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        stmt = "".join(current).strip()
        if stmt:
            parts.append(stmt)
    return [p for p in parts if p and not p.startswith("--")]


# ─── Local Row wrapper (dict with attribute access) ──────────────────
class _LocalRecord(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def get(self, key, default=None):
        return dict.get(self, key, default)


# ─── Local Connection wrapper (mimics asyncpg connection) ────────────
class _LocalConnection:
    def __init__(self, conn, lock):
        self._conn = conn
        self._lock = lock

    async def execute(self, sql: str, *args) -> str:
        sql_t, params = _translate_sql_with_args(sql, list(args) if args else [])

        def _run():
            with self._lock:
                try:
                    self._conn.execute(sql_t, params)
                except Exception:
                    try:
                        self._conn.execute(sql_t)
                    except Exception:
                        pass
                return "OK"

        return await asyncio.to_thread(_run)

    async def fetch(self, sql: str, *args):
        sql_t, params = _translate_sql_with_args(sql, list(args) if args else [])

        def _run():
            with self._lock:
                cur = self._conn.execute(sql_t, params)
                if not cur.description:
                    return []
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                return [_LocalRecord(zip(cols, row)) for row in rows]

        return await asyncio.to_thread(_run)

    async def fetchrow(self, sql: str, *args):
        rows = await self.fetch(sql, *args)
        return rows[0] if rows else None

    async def fetchval(self, sql: str, *args):
        row = await self.fetchrow(sql, *args)
        if row is None:
            return None
        if isinstance(row, dict) and row:
            return next(iter(row.values()), None)
        return row

    async def executemany(self, sql: str, batch) -> str:
        for row in batch:
            sql_t, args_t = _translate_sql_with_args(sql, list(row))
            def _run(sql=sql_t, a=args_t):
                with self._lock:
                    self._conn.execute(sql, a)
            await asyncio.to_thread(_run)
        return "OK"

    def transaction(self):
        """Mimic asyncpg conn.transaction() — DuckDB auto-commits."""
        class _TxCtx:
            async def __aenter__(self_):
                return self_
            async def __aexit__(self_, *exc):
                return False
        return _TxCtx()


# ─── Local Pool wrapper (mimics asyncpg Pool) ────────────────────────
class _LocalPool:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = duckdb.connect(db_path, read_only=False)
        self._lock = threading.Lock()

    def acquire(self):
        outer = self

        class _Ctx:
            async def __aenter__(self_):
                return _LocalConnection(outer._conn, outer._lock)

            async def __aexit__(self_, *exc):
                return False

        return _Ctx()

    async def close(self):
        def _run():
            with self._lock:
                try:
                    self._conn.close()
                except Exception:
                    pass

        await asyncio.to_thread(_run)


# ─── Migration runner ────────────────────────────────────────────────
def _apply_migrations(conn, lock):
    """Apply each migrations/*.sql file (idempotent)."""
    try:
        mig_dir = Path(__file__).resolve().parent.parent.parent / "migrations"
    except Exception:
        return

    if not mig_dir.exists():
        print(f"[state] migrations dir not found: {mig_dir}", file=sys.stderr)
        return

    for mig in sorted(mig_dir.glob("*.sql")):
        try:
            sql = mig.read_text(encoding="utf-8")
            for stmt in _split_statements(sql):
                try:
                    # Handle BIGSERIAL: create sequence, translate column
                    if re.search(r"\bBIGSERIAL\b", stmt, re.IGNORECASE):
                        m = re.search(
                            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
                            stmt, re.IGNORECASE,
                        )
                        if m:
                            table = m.group(1)
                            seq = f"{table}_id_seq"
                            try:
                                with lock:
                                    conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq}")
                            except Exception:
                                pass
                            stmt = re.sub(
                                r"\bBIGSERIAL\b",
                                f"BIGINT DEFAULT nextval('{seq}')",
                                stmt, flags=re.IGNORECASE,
                            )
                    stmt = _translate_ddl(stmt)
                    if not stmt.strip():
                        continue  # translation skipped this statement
                    with lock:
                        conn.execute(stmt)
                except Exception as e:
                    msg = str(e).lower()
                    if "already exists" in msg or "duplicate" in msg:
                        continue
                    print(f"[state] {mig.name} stmt skipped: {type(e).__name__}: {e}",
                          file=sys.stderr)
        except Exception as e:
            print(f"[state] migration {mig.name} failed: {e}", file=sys.stderr)


# ─── init_pool ───────────────────────────────────────────────────────
async def init_pool(dsn: Optional[str] = None) -> bool:
    global _pool, _last_error, _pool_kind
    if _pool is not None:
        return True

    url = dsn or os.getenv("NEON_DATABASE_URL")
    force_local = os.getenv("SUNNYWARE_USE_LOCAL_DB", "").lower() in ("1", "true", "yes")

    # ── DuckDB path: forced OR no Neon URL ──
    if force_local or not url:
        if not _HAS_DUCKDB:
            _last_error = "Neither NEON_DATABASE_URL nor duckdb available"
            print(f"[state] {_last_error}", file=sys.stderr)
            return False
        try:
            data_dir = Path(os.getenv("SUNNYWARE_DATA_DIR", "/data"))
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "sunnyware.duckdb")

            # Attempt 1: open existing DB, apply migrations
            try:
                _pool = _LocalPool(db_path)
                _pool_kind = "duckdb"
                _apply_migrations(_pool._conn, _pool._lock)
                print(f"[state] Local DuckDB pool ready (existing DB): {db_path}", file=sys.stderr)
                _last_error = None
                return True
            except Exception as e1:
                # Migration or open failed — likely stale/corrupt schema
                print(f"[state] Existing DB failed: {type(e1).__name__}: {e1}. Attempting rebuild...", file=sys.stderr)
                try:
                    if _pool is not None:
                        _pool._conn.close()
                except Exception:
                    pass
                _pool = None
                # Backup + delete the stale DB
                try:
                    if Path(db_path).exists():
                        bak = db_path + ".stale"
                        Path(db_path).rename(bak)
                        print(f"[state] Backed up stale DB to {bak}", file=sys.stderr)
                except Exception as e2:
                    print(f"[state] Could not backup stale DB: {e2}", file=sys.stderr)

            # Attempt 2: fresh DB
            _pool = _LocalPool(db_path)
            _pool_kind = "duckdb"
            try:
                _apply_migrations(_pool._conn, _pool._lock)
                print(f"[state] Local DuckDB pool ready (fresh DB): {db_path}", file=sys.stderr)
            except Exception as e_mig:
                # Migrations still fail — but keep the pool alive
                print(f"[state] Migrations partially failed (pool survives): {type(e_mig).__name__}: {e_mig}", file=sys.stderr)
            _last_error = None
            return True
        except Exception as e:
            _last_error = f"DuckDB init failed: {type(e).__name__}: {e}"
            print(f"[state] {_last_error}", file=sys.stderr)
            _pool = None
            return False

    # ── Postgres path (existing) ──
    if not _HAS_ASYNCPG:
        _last_error = "asyncpg not installed"
        return False

    try:
        host = url.split("@")[1].split("/")[0] if "@" in url else "?"
        print(f"[state] init_pool url_len={len(url)} host={host}", file=sys.stderr)
    except Exception:
        pass

    try:
        _pool = await asyncio.wait_for(
            asyncpg.create_pool(
                url,
                min_size=1,
                max_size=5,
                command_timeout=30,
                statement_cache_size=0,
                timeout=15,
            ),
            timeout=20,
        )
        _pool_kind = "postgres"
        print("[state] asyncpg pool created OK", file=sys.stderr)
        _last_error = None
        return True
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e}"
        print(f"[state] pool init failed: {_last_error}", file=sys.stderr)
        _pool = None
        return False


async def close_pool() -> None:
    global _pool, _pool_kind
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            pass
        _pool = None
        _pool_kind = None


def get_pool():
    return _pool


def get_last_error() -> Optional[str]:
    return _last_error


def get_pool_kind() -> Optional[str]:
    return _pool_kind


async def health_check() -> dict:
    if _pool is None:
        return {"status": "not_initialized", "error": _last_error or "pool is None"}
    try:
        async with _pool.acquire() as conn:
            ver = await conn.fetchval("SELECT version()")
            return {
                "status": "ok",
                "kind": _pool_kind,
                "version": str(ver).split(",")[0] if ver else "unknown",
            }
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}
