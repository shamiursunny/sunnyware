import pandas as pd
import json
from pathlib import Path
from .. import paths

class AggregateMarketDataTool:
    name = "aggregate_market_data"
    description = "Fetch stock data from multiple providers, unify into a local database, and return a summary."
    keywords = ["aggregate market data", "multi provider stock", "unify stock data"]
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock ticker (e.g., AAPL)"}
        },
        "required": ["symbol"]
    }

    async def run(self, symbol: str, kind: str = "sandbox") -> dict:
        from .finnhub_quote import FinnhubTool as FinnhubQuoteTool
        from .tiingo_prices import TiingoPricesTool
        
        results = {}
        
        # 1. Fetch Finnhub
        try:
            fh = FinnhubQuoteTool()
            results["finnhub"] = await fh.run(symbol)
        except Exception as e:
            results["finnhub"] = {"error": str(e)}

        # 2. Fetch Tiingo
        try:
            tg = TiingoPricesTool()
            results["tiingo"] = await tg.run(symbol)
        except Exception as e:
            results["tiingo"] = {"error": str(e)}

        # 3. Save to SQLite
        base = paths.workspace()
        db_path = base / f"{symbol}_market.db"
        
        rows = []
        for provider, data in results.items():
            if isinstance(data, dict) and "error" not in data:
                # Extract common fields
                row = {
                    "provider": provider,
                    "symbol": symbol,
                    "price": data.get("c") or data.get("close") or data.get("price") or 0,
                    "high": data.get("h") or data.get("high") or 0,
                    "low": data.get("l") or data.get("low") or 0
                }
                rows.append(row)
        
        df = pd.DataFrame(rows)
        if not df.empty:
            import sqlite3
            conn = sqlite3.connect(db_path)
            df.to_sql(f"{symbol}_quotes", conn, if_exists="replace", index=False)
            conn.close()
            return {"ok": True, "message": f"Unified data saved to {db_path.name}", "records": len(rows), "data": rows}
        
        return {"error": "No data could be fetched from any provider."}
