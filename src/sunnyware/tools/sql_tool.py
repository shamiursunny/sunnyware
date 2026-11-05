import pandas as pd
import sqlite3
from pathlib import Path
from .. import paths

class QuerySqliteTool:
    name = "query_sqlite"
    description = "Run a SQL query on a CSV or Excel file. It automatically loads the file into a temporary SQLite database."
    keywords = ["query sql", "run sql", "sqlite", "database query", "sql select"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "The CSV or Excel file to query"},
            "sql_query": {"type": "string", "description": "The SQL query to execute (e.g., SELECT * FROM data WHERE ...)"},
            "table_name": {"type": "string", "description": "Name of the table (defaults to 'data')"}
        },
        "required": ["filename", "sql_query"]
    }

    async def run(self, filename: str, sql_query: str, table_name: str = "data", kind: str = "sandbox") -> dict:
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists():
            return {"error": f"File {filename} not found in {kind}"}

        try:
            if target.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(target)
            else:
                df = pd.read_csv(target)
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}"}

        try:
            # Use in-memory SQLite
            conn = sqlite3.connect(":memory:")
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            
            # Execute query
            res_df = pd.read_sql_query(sql_query, conn)
            conn.close()
            
            if res_df.empty:
                return {"ok": True, "result": "Query returned 0 rows.", "row_count": 0}
            
            # Truncate if too large (max 50 rows for the LLM context)
            truncated = False
            if len(res_df) > 50:
                res_df = res_df.head(50)
                truncated = True
                
            return {
                "ok": True,
                "row_count": len(res_df),
                "truncated": truncated,
                "columns": list(res_df.columns),
                "data": res_df.to_dict(orient="records")
            }
        except Exception as e:
            return {"error": f"SQL execution failed: {str(e)}"}
