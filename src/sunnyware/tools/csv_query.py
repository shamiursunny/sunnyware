# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""CSV / Parquet / JSON query tool — DuckDB over workspace files (Part 50).

Streams data straight from disk so we can handle files larger than RAM.
Only SELECT / WITH queries are permitted. Path is jailed to the workspace.
"""
import os
import re
from pathlib import Path

try:
    import duckdb  # type: ignore
    _HAS_DUCK = True
except Exception:
    _HAS_DUCK = False


_ALLOWED_PREFIX = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_ALLOWED_EXT = {".csv", ".tsv", ".parquet", ".json", ".jsonl", ".ndjson"}


def _workspace_root() -> Path:
    # Mirrors read_file / write_file: env override, else /data/workspace
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


class CsvQueryTool:
    name = "csv_query"
    description = "Query a CSV file using SQL SELECT. Triggers: CSV, spreadsheet, query data, select from csv. Input: filepath (e.g., data.csv) and SQL query. Returns matching rows."."
    )
    parameters = {
        "file": {
            "type": "string",
            "description": "File name (relative to workspace, e.g. 'sales.csv')",
            "required": True,
        },
        "sql": {
            "type": "string",
            "description": (
                "SELECT or WITH query. Reference the file as a table named "
                "after its stem. Example: SELECT region, SUM(amount) FROM sales "
                "GROUP BY region ORDER BY 2 DESC"
            ),
            "required": True,
        },
        "limit": {
            "type": "integer",
            "description": "Max rows to return (default 200, max 10000)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_DUCK:
            return {"error": "duckdb not installed in this environment"}

        fname = (args.get("file") or "").strip()
        sql = (args.get("sql") or "").strip()
        if not fname or not sql:
            return {"error": "file and sql are required"}

        try:
            limit = max(1, min(int(args.get("limit") or 200), 10000))
        except (TypeError, ValueError):
            return {"error": "limit must be an integer"}

        # Jail path to workspace
        root = _workspace_root()
        candidate = (root / fname).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return {"error": "file must live inside the workspace"}

        if not candidate.exists():
            return {"error": f"file not found: {fname}"}

        ext = candidate.suffix.lower()
        if ext not in _ALLOWED_EXT:
            return {"error": f"unsupported file type: {ext}"}

        if not _ALLOWED_PREFIX.match(sql):
            return {"error": "only SELECT / WITH queries are allowed"}

        stem = re.sub(r"[^A-Za-z0-9_]", "_", candidate.stem)
        path_sql = str(candidate).replace("'", "''")

        if ext in (".csv", ".tsv"):
            reader = f"read_csv_auto('{path_sql}', header=true)"
        elif ext == ".parquet":
            reader = f"read_parquet('{path_sql}')"
        else:
            reader = f"read_json_auto('{path_sql}')"

        # Cap rows server-side
        capped_sql = f"SELECT * FROM ({sql}) AS _q LIMIT {limit}"

        try:
            con = duckdb.connect(":memory:")
            con.execute(f"CREATE VIEW {stem} AS SELECT * FROM {reader}")
            rel = con.execute(capped_sql)
            columns = [d[0] for d in rel.description]
            rows = rel.fetchall()
            con.close()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

        # JSON-safe coercion
        def _coerce(v):
            try:
                if v is None or isinstance(v, (str, int, float, bool)):
                    return v
                return str(v)
            except Exception:
                return str(v)

        return {
            "file": fname,
            "columns": columns,
            "row_count": len(rows),
            "truncated": len(rows) >= limit,
            "rows": [[_coerce(c) for c in r] for r in rows],
        }
