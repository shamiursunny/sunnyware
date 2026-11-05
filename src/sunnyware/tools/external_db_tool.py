from pathlib import Path

class QueryExternalDbTool:
    name = "query_external_db"
    description = "Run a SQL query against an external PostgreSQL or MySQL database using a connection string."
    keywords = ["external database", "postgres query", "mysql query", "connect to database"]
    parameters = {
        "type": "object",
        "properties": {
            "connection_string": {"type": "string", "description": "The DB connection string (e.g., postgresql://user:pass@host/db)"},
            "sql_query": {"type": "string", "description": "The SQL query to execute"},
            "db_type": {"type": "string", "enum": ["postgres", "mysql"], "description": "Database type"}
        },
        "required": ["connection_string", "sql_query", "db_type"]
    }

    async def run(self, connection_string: str, sql_query: str, db_type: str = "postgres") -> dict:
        import pandas as pd
        try:
            from sqlalchemy import create_engine
            if db_type == "mysql":
                connection_string = connection_string.replace("mysql://", "mysql+pymysql://")
            engine = create_engine(connection_string)
            df = pd.read_sql_query(sql_query, engine)
            engine.dispose()
            
            if df.empty:
                return {"ok": True, "result": "Query returned 0 rows.", "row_count": 0}
            
            truncated = len(df) > 50
            if truncated:
                df = df.head(50)
                
            return {
                "ok": True,
                "row_count": len(df),
                "truncated": truncated,
                "columns": list(df.columns),
                "data": df.to_dict(orient="records")
            }
        except Exception as e:
            return {"error": f"External DB query failed: {str(e)}"}
