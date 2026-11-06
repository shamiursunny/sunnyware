import os
import httpx
import asyncio
import time
from pathlib import Path
from .. import paths
import pandas as pd

class LiveMarketStreamTool:
    name = "live_market_stream"
    description = "Stream live stock prices via REST polling (Finnhub)."
    keywords = ["live market", "stream prices", "real-time stock", "live stream"]
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock ticker (e.g., AAPL)"},
            "duration_seconds": {"type": "integer", "description": "How long to stream", "default": 10}
        },
        "required": ["symbol"]
    }

    async def run(self, symbol: str, duration_seconds: int = 10) -> dict:
        print(f"[live_market_stream] Starting REST polling for {symbol}", flush=True)
        api_key = os.environ.get("FINNHUB_API_KEY")
        if not api_key:
            return {"error": "FINNHUB_API_KEY not set."}

        ticks = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                end_time = time.time() + min(duration_seconds, 10)
                while time.time() < end_time:
                    try:
                        resp = await client.get(
                            "https://finnhub.io/api/v1/quote",
                            params={"symbol": symbol.upper(), "token": api_key}
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("c"):
                                ticks.append({
                                    "timestamp": int(time.time()),
                                    "symbol": symbol.upper(),
                                    "price": data.get("c"),
                                    "volume": data.get("v", 0)
                                })
                    except Exception as e:
                        print(f"[live_market_stream] Poll error: {e}", flush=True)
                    await asyncio.sleep(1)
        except Exception as e:
            return {"error": f"REST polling failed: {e}"}

        if not ticks:
            return {"error": f"No ticks collected for {symbol}."}

        df = pd.DataFrame(ticks)
        base = paths.workspace()
        out_file = base / f"{symbol.upper()}_live.csv"
        df.to_csv(out_file, index=False)

        return {
            "ok": True,
            "message": f"Streamed {len(ticks)} ticks for {symbol.upper()}",
            "file": out_file.name,
            "preview": ticks[:3]
        }
