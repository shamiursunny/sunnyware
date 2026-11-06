import pandas as pd
from pathlib import Path
from .. import paths

class ProChartTool:
    name = "pro_chart"
    description = "Generate professional financial (candlestick) or statistical (heatmap) charts."
    keywords = ["pro chart", "candlestick chart", "financial chart", "seaborn heatmap"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "chart_type": {"type": "string", "enum": ["candlestick", "correlation"]}
        },
        "required": ["filename", "chart_type"]
    }

    async def run(self, filename: str, chart_type: str, kind: str = "sandbox") -> dict:
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists():
            return {"error": f"File {filename} not found"}

        try:
            df = pd.read_csv(target)
            df.columns = [c.lower() for c in df.columns]
            
            if chart_type == "candlestick":
                try:
                    import mplfinance as mpf
                except ImportError:
                    return {"error": "Library 'mplfinance' not installed"}

                required = ['open', 'high', 'low', 'close']
                if not all(col in df.columns for col in required):
                    return {"error": f"Candlestick requires columns: {required}. Available: {list(df.columns)}"}

                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)

                df_mpf = df[['open', 'high', 'low', 'close']].copy()
                if 'volume' in df.columns:
                    df_mpf['volume'] = df['volume']

                out_name = f"pro_candlestick_{target.stem}.png"
                out_path = base / out_name
                
                mpf.plot(df_mpf, type='candle', style='charles', 
                         title=f"Candlestick: {target.stem}", 
                         volume=True if 'volume' in df_mpf.columns else False,
                         savefig=dict(fname=str(out_path), dpi=150, bbox_inches='tight'))
                
                return {"ok": True, "message": f"Professional Candlestick chart saved to {out_name}"}

            elif chart_type == "correlation":
                try:
                    import seaborn as sns
                    import matplotlib.pyplot as plt
                except ImportError:
                    return {"error": "Libraries 'seaborn' or 'matplotlib' not installed"}

                numeric_df = df.select_dtypes(include=['number'])
                if numeric_df.empty:
                    return {"error": "No numeric columns found for correlation"}

                plt.figure(figsize=(10, 8))
                corr = numeric_df.corr()
                sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f")
                plt.title(f"Correlation Heatmap - {target.stem}")
                plt.tight_layout()

                out_name = f"pro_heatmap_{target.stem}.png"
                out_path = base / out_name
                plt.savefig(out_path, dpi=150, bbox_inches='tight')
                plt.close()
                
                return {"ok": True, "message": f"Professional Heatmap saved to {out_name}"}

        except Exception as e:
            return {"error": str(e)}
