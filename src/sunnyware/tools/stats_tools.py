"""Direct statistical tools — 0 LLM tokens, routed via keyword_router."""
from pathlib import Path
from .. import paths


class DataStatsTool:
    name = "data_stats"
    description = "Compute statistical summary (mean, median, std, min, max) for a list of numbers or a CSV column."
    keywords = ["mean", "median", "average", "std", "min", "max", "stats", "statistics"]
    parameters = {
        "type": "object",
        "properties": {
            "values": {"type": "array", "items": {"type": "number"}, "description": "List of numbers"},
            "filename": {"type": "string", "description": "Optional CSV file to read from"},
            "column": {"type": "string", "description": "Optional column name (with filename)"},
        },
        "required": [],
    }

    async def run(self, values=None, filename=None, column=None, kind="sandbox"):
        import numpy as np
        import pandas as pd

        if filename:
            base = paths.sandbox() if kind == "sandbox" else paths.workspace()
            target = base / Path(filename).name
            if not target.exists():
                return {"error": f"File {filename} not found in {kind}"}
            try:
                df = pd.read_excel(target) if target.suffix.lower() in [".xlsx", ".xls"] else pd.read_csv(target)
            except Exception as e:
                return {"error": f"Failed to read file: {e}"}
            if column and column not in df.columns:
                return {"error": f"Column '{column}' not found. Available: {list(df.columns)}"}
            if column:
                values = df[column].dropna().tolist()
            elif len(df.columns) == 1:
                values = df.iloc[:, 0].dropna().tolist()
            else:
                return {"error": f"Multiple columns in file. Specify `column`. Available: {list(df.columns)}"}

        if not values:
            return {"error": "No values provided. Pass `values` or `filename`+`column`."}

        try:
            arr = np.asarray(values, dtype=float)
        except Exception as e:
            return {"error": f"Invalid numeric data: {e}"}

        return {
            "ok": True,
            "count": int(len(arr)),
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "sum": float(np.sum(arr)),
            "q25": float(np.percentile(arr, 25)),
            "q75": float(np.percentile(arr, 75)),
        }


class DataDescribeTool:
    name = "data_describe"
    description = "Full pandas-style statistical summary of a CSV/Excel file."
    keywords = ["describe", "data describe", "dataset summary", "summary of"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "kind": {"type": "string", "enum": ["sandbox", "workspace"]},
        },
        "required": ["filename"],
    }

    async def run(self, filename, kind="sandbox"):
        import pandas as pd
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists():
            return {"error": f"File {filename} not found in {kind}"}
        try:
            df = pd.read_excel(target) if target.suffix.lower() in [".xlsx", ".xls"] else pd.read_csv(target)
        except Exception as e:
            return {"error": f"Failed to read: {e}"}

        desc = df.describe(include="all").to_dict()
        return {
            "ok": True,
            "shape": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
            "columns": list(df.columns),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "missing": {c: int(df[c].isna().sum()) for c in df.columns},
            "describe": desc,
        }


class DataCorrelationTool:
    name = "data_correlation"
    description = "Pearson correlation between two numeric arrays or two CSV columns."
    keywords = ["correlation", "correlate", "corr", "relationship between"]
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "array", "items": {"type": "number"}},
            "y": {"type": "array", "items": {"type": "number"}},
            "filename": {"type": "string"},
            "col_x": {"type": "string"},
            "col_y": {"type": "string"},
        },
        "required": [],
    }

    async def run(self, x=None, y=None, filename=None, col_x=None, col_y=None, kind="sandbox"):
        import numpy as np
        import pandas as pd
        if filename:
            base = paths.sandbox() if kind == "sandbox" else paths.workspace()
            target = base / Path(filename).name
            if not target.exists():
                return {"error": f"File {filename} not found"}
            try:
                df = pd.read_excel(target) if target.suffix.lower() in [".xlsx", ".xls"] else pd.read_csv(target)
            except Exception as e:
                return {"error": f"Read failed: {e}"}
            if not col_x or not col_y or col_x not in df.columns or col_y not in df.columns:
                return {"error": f"Column not found. Available: {list(df.columns)}"}
            x = df[col_x].dropna().tolist()
            y = df[col_y].dropna().tolist()

        if not x or not y or len(x) != len(y):
            return {"error": "Provide equal-length `x` and `y`, or `filename`+`col_x`+`col_y`."}
        try:
            xa, ya = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
            r = float(np.corrcoef(xa, ya)[0, 1])
        except Exception as e:
            return {"error": f"Correlation failed: {e}"}
        return {"ok": True, "pearson_r": r, "n": int(len(xa))}


class CsvGroupByTool:
    name = "csv_groupby"
    description = "Group a CSV/Excel by a column and compute an aggregate on another column."
    keywords = ["group by", "groupby", "aggregate", "sum by", "mean by"]
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "group_col": {"type": "string"},
            "agg_col": {"type": "string"},
            "agg_func": {"type": "string", "enum": ["sum", "mean", "count", "min", "max"]},
            "kind": {"type": "string", "enum": ["sandbox", "workspace"]},
        },
        "required": ["filename", "group_col", "agg_col", "agg_func"],
    }

    async def run(self, filename, group_col, agg_col, agg_func="sum", kind="sandbox"):
        import pandas as pd
        base = paths.sandbox() if kind == "sandbox" else paths.workspace()
        target = base / Path(filename).name
        if not target.exists():
            return {"error": f"File {filename} not found"}
        try:
            df = pd.read_excel(target) if target.suffix.lower() in [".xlsx", ".xls"] else pd.read_csv(target)
        except Exception as e:
            return {"error": f"Read failed: {e}"}
        if group_col not in df.columns or agg_col not in df.columns:
            return {"error": f"Columns not found. Available: {list(df.columns)}"}
        try:
            result = df.groupby(group_col)[agg_col].agg(agg_func).reset_index()
        except Exception as e:
            return {"error": f"GroupBy failed: {e}"}
        return {
            "ok": True,
            "group_col": group_col,
            "agg_col": agg_col,
            "agg_func": agg_func,
            "rows": result.to_dict(orient="records"),
        }
