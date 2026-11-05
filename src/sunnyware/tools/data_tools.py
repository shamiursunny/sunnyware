from pathlib import Path
from .. import paths

class GenerateChartTool:
    name = "generate_chart"
    description = "Generate a bar, line, or pie chart from a CSV or Excel file and save it as a PNG."
    keywords = ["generate chart", "create graph", "plot data", "make a chart"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "The CSV or Excel file to chart"},
            "chart_type": {"type": "string", "enum": ["bar", "line", "pie"], "description": "Type of chart"},
            "x_column": {"type": "string", "description": "Column name for the X-axis (or labels for pie)"},
            "y_column": {"type": "string", "description": "Column name for the Y-axis (or values for pie)"},
            "title": {"type": "string", "description": "Title of the chart"}
        },
        "required": ["filename", "chart_type", "x_column", "y_column"]
    }

    async def run(self, filename: str, chart_type: str, x_column: str, y_column: str, title: str = "Chart", kind: str = "sandbox") -> dict:
        import pandas as pd
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

        if x_column not in df.columns or y_column not in df.columns:
            return {"error": f"Columns not found. Available: {list(df.columns)}"}

        try:
            import matplotlib
            matplotlib.use('Agg') # Headless mode
            import matplotlib.pyplot as plt
            
            plt.figure(figsize=(10, 6))
            if chart_type == "bar":
                plt.bar(df[x_column], df[y_column])
            elif chart_type == "line":
                plt.plot(df[x_column], df[y_column])
            elif chart_type == "pie":
                plt.pie(df[y_column], labels=df[x_column], autopct='%1.1f%%')
            
            plt.title(title)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            out_name = f"chart_{target.stem}.png"
            out_path = paths.sandbox() / out_name
            plt.savefig(out_path)
            plt.close()
            
            return {"ok": True, "message": f"Chart saved to sandbox as {out_name}", "file": out_name}
        except Exception as e:
            return {"error": f"Failed to generate chart: {str(e)}"}

class CleanDatasetTool:
    name = "clean_dataset"
    description = "Clean a dataset by dropping nulls, filling missing values, and saving to a new file."
    keywords = ["clean dataset", "clean data", "fix nulls", "clean csv"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "drop_nulls": {"type": "boolean", "description": "Drop rows with any missing values"},
            "fill_value": {"type": "string", "description": "Value to fill missing cells with (e.g., '0', 'Unknown')"},
            "output_filename": {"type": "string", "description": "Name of the cleaned file to save"}
        },
        "required": ["filename", "output_filename"]
    }

    async def run(self, filename: str, output_filename: str, drop_nulls: bool = False, fill_value: str = None, kind: str = "sandbox") -> dict:
        import pandas as pd
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

        original_rows = len(df)
        if drop_nulls:
            df = df.dropna()
        if fill_value is not None:
            df = df.fillna(fill_value)

        out_path = paths.sandbox() / Path(output_filename).name
        try:
            if out_path.suffix.lower() in [".xlsx", ".xls"]:
                df.to_excel(out_path, index=False)
            else:
                df.to_csv(out_path, index=False)
        except Exception as e:
            return {"error": f"Failed to save cleaned file: {str(e)}"}

        return {
            "ok": True,
            "message": f"Cleaned dataset saved as {out_path.name}",
            "original_rows": original_rows,
            "new_rows": len(df)
        }
