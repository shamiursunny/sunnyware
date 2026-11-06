import pandas as pd
import numpy as np
from pathlib import Path
from .. import paths

class TechnicalAnalysisTool:
    name = "technical_analysis"
    description = "Calculate RSI, MACD, SMA, EMA, and Bollinger Bands from a stock CSV."
    keywords = ["technical analysis", "rsi", "macd", "moving average", "bollinger"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "CSV file with stock data"},
            "indicators": {"type": "string", "description": "Comma-separated list: rsi,macd,sma,bbands"}
        },
        "required": ["filename"]
    }

    async def run(self, filename: str, indicators: str = "rsi,macd,sma", kind: str = "sandbox") -> dict:
        try:
            import ta
        except ImportError:
            return {"error": "Library 'ta' is not installed. Run: pip install ta"}

        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists():
            # Fallback to workspace if not found in sandbox
            target = paths.workspace() / Path(filename).name
            base = paths.workspace()
            if not target.exists():
                return {"error": f"File {filename} not found in sandbox or workspace"}

        try:
            df = pd.read_csv(target)
            cols = [c.lower() for c in df.columns]
            if 'close' not in cols:
                return {"error": "CSV must contain a 'close' column"}
            
            close_col = df.columns[cols.index('close')]
            close_series = df[close_col]
            
            results = {}
            req_ind = [i.strip().lower() for i in indicators.split(",")]
            
            if "rsi" in req_ind:
                df['RSI'] = ta.momentum.RSIIndicator(close_series).rsi()
                results["current_rsi"] = round(float(df['RSI'].iloc[-1]), 2)
            if "macd" in req_ind:
                macd = ta.trend.MACD(close_series)
                df['MACD'] = macd.macd()
                df['MACD_Signal'] = macd.macd_signal()
                results["macd"] = round(float(df['MACD'].iloc[-1]), 2)
                results["macd_signal"] = round(float(df['MACD_Signal'].iloc[-1]), 2)
            if "sma" in req_ind:
                df['SMA_20'] = ta.trend.SMAIndicator(close_series, window=20).sma_indicator()
                results["sma_20"] = round(float(df['SMA_20'].iloc[-1]), 2)
            if "bbands" in req_ind:
                bb = ta.volatility.BollingerBands(close_series)
                df['BB_High'] = bb.bollinger_hband()
                df['BB_Low'] = bb.bollinger_lband()
                results["bb_high"] = round(float(df['BB_High'].iloc[-1]), 2)
                results["bb_low"] = round(float(df['BB_Low'].iloc[-1]), 2)

            out_name = f"ta_{target.stem}.csv"
            df.to_csv(base / out_name, index=False)
            
            return {"ok": True, "message": f"TA calculated. Saved to {out_name}", "metrics": results}
        except Exception as e:
            return {"error": str(e)}

class MLForecastTool:
    name = "ml_forecast"
    description = "Use Scikit-Learn to predict future prices or trends from CSV data."
    keywords = ["ml forecast", "predict price", "machine learning forecast", "scikit learn"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "target_column": {"type": "string"},
            "periods": {"type": "integer"}
        },
        "required": ["filename", "target_column", "periods"]
    }

    async def run(self, filename: str, target_column: str, periods: int = 5, kind: str = "sandbox") -> dict:
        try:
            from sklearn.linear_model import LinearRegression
        except ImportError:
            return {"error": "Library 'scikit-learn' is not installed"}

        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists():
            # Fallback to workspace if not found in sandbox
            target = paths.workspace() / Path(filename).name
            base = paths.workspace()
            if not target.exists():
                return {"error": f"File {filename} not found in sandbox or workspace"}

        try:
            df = pd.read_csv(target)
            cols = [c.lower() for c in df.columns]
            target_col_actual = df.columns[cols.index(target_column.lower())] if target_column.lower() in cols else target_column
            
            if target_col_actual not in df.columns:
                return {"error": f"Column {target_column} not found. Available: {list(df.columns)}"}
            
            df = df.dropna(subset=[target_col_actual])
            X = np.arange(len(df)).reshape(-1, 1)
            y = df[target_col_actual].values

            model = LinearRegression()
            model.fit(X, y)

            future_X = np.arange(len(df), len(df) + periods).reshape(-1, 1)
            predictions = model.predict(future_X)

            forecast_df = pd.DataFrame({
                "step": range(1, periods + 1),
                "predicted_" + target_col_actual: predictions
            })
            out_name = f"forecast_{target.stem}.csv"
            forecast_df.to_csv(base / out_name, index=False)

            return {
                "ok": True, 
                "message": f"Forecast generated using Linear Regression. Saved to {out_name}",
                "predictions": [round(float(p), 2) for p in predictions]
            }
        except Exception as e:
            return {"error": str(e)}
