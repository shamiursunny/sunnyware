import os
import json
import asyncio
import time
from pathlib import Path
from .. import paths
import pandas as pd

class LiveMarketStreamTool:
    name = "live_market_stream"
    description = "Stream live stock prices via WebSocket (or REST fallback)."
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
        print(f"[live_market_stream] Starting for {symbol}", flush=True)
        api_key = os.environ.get("FINNHUB_API_KEY")
        if not api_key:
            return {"error": "FINNHUB_API_KEY not set."}

        ticks = []
        ws_error = None

        # Try WebSocket first
        try:
            import websockets
            url = f"wss://ws.finnhub.io?token={api_key}"
            print(f"[live_market_stream] Connecting to WebSocket...", flush=True)
            async with websockets.connect(url, timeout=10, ping_interval=20) as ws:
                await ws.send(json.dumps({"type": "subscribe", "symbol": symbol.upper()}))
                print(f"[live_market_stream] Subscribed to {symbol}", flush=True)
                end_time = time.time() + duration_seconds
                while time.time() < end_time:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(msg)
                        if data.get("type") == "trade":
                            for trade in data.get("data", []):
                                ticks.append({
                                    "timestamp": trade.get("t"),
                                    "symbol": trade.get("s"),
                                    "price": trade.get("p"),
                                    "volume": trade.get("v")
                                })
                    except asyncio.TimeoutError:
                        pass
                await ws.send(json.dumps({"type": "unsubscribe", "symbol": symbol.upper()}))
        except Exception as e:
            ws_error = str(e)
            print(f"[live_market_stream] WebSocket failed: {e}", flush=True)

        # Fallback: REST polling
        if not ticks:
            print(f"[live_market_stream] Falling back to REST polling...", flush=True)
            import httpx
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    end_time = time.time() + min(duration_seconds, 5)  # REST polling for max 5s
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
                            print(f"[live_market_stream] REST poll error: {e}", flush=True)
                        await asyncio.sleep(1)
            except Exception as e:
                return {"error": f"Both WebSocket and REST failed. WS: {ws_error}. REST: {e}"}

        if not ticks:
            return {"error": f"No ticks collected for {symbol}. WebSocket error: {ws_error}"}

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
