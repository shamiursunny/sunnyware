# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Data quality report tool (Part 80).

Scan a CSV/XLSX/TSV/Parquet file in the workspace and report:
  - row count, column count, dtypes
  - per-column: nulls, uniques, min/max/mean for numerics
  - duplicates, outlier counts (IQR), type-mismatch counts
  - distribution shape (skew approx)
"""
import csv
import os
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
    import numpy as np
    _HAS_PANDAS = True
except Exception:
    _HAS_PANDAS = False


_MAX_ROWS = 200_000
_MAX_COLS = 200
_TOP_UNIQUES = 5


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _load_df(path: Path) -> "pd.DataFrame":
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext == ".tsv":
        return pd.read_csv(path, sep="\t")
    if ext == ".xlsx":
        return pd.read_excel(path)
    if ext == ".parquet":
        return pd.read_parquet(path)
    if ext == ".json":
        return pd.read_json(path)
    raise ValueError("unsupported file type: " + ext)


def _col_report(s: "pd.Series") -> dict:
    n = len(s)
    nulls = int(s.isna().sum())
    non_null = n - nulls
    uniques = int(s.nunique(dropna=True))
    report = {
        "dtype": str(s.dtype),
        "nulls": nulls,
        "null_pct": round(100.0 * nulls / n, 2) if n else 0.0,
        "uniques": uniques,
        "non_null": non_null,
    }

    # Top uniques (if small cardinality)
    if 1 < uniques <= 20:
        try:
            vc = s.value_counts().head(_TOP_UNIQUES)
            report["top_values"] = [
                {"value": str(k)[:60], "count": int(v)} for k, v in vc.items()
            ]
        except Exception:
            pass

    # Numeric stats
    if pd.api.types.is_numeric_dtype(s):
        try:
            nn = s.dropna()
            if len(nn) > 0:
                report["min"] = float(nn.min())
                report["max"] = float(nn.max())
                report["mean"] = round(float(nn.mean()), 4)
                report["std"] = round(float(nn.std()), 4)
                report["median"] = float(nn.median())
                # outliers via IQR
                q1, q3 = nn.quantile(0.25), nn.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                    report["outliers_iqr"] = int(((nn < lo) | (nn > hi)).sum())
                else:
                    report["outliers_iqr"] = 0
                # skew
                try:
                    report["skew"] = round(float(nn.skew()), 3)
                except Exception:
                    pass
        except Exception:
            pass

    # String stats
    if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
        try:
            nn = s.dropna().astype(str)
            if len(nn) > 0:
                report["min_length"] = int(nn.str.len().min())
                report["max_length"] = int(nn.str.len().max())
                report["avg_length"] = round(float(nn.str.len().mean()), 1)
                # suspicious: leading/trailing whitespace
                report["has_whitespace"] = bool(
                    ((nn != nn.str.strip()).sum()) > 0
                )
        except Exception:
            pass

    return report


class DataQualityReportTool:
    name = "data_quality_report"
    description = (
        "Scan a data file (CSV/TSV/XLSX/Parquet/JSON) in the workspace and "
        "return a data-quality report: per-column nulls, uniques, min/max/"
        "mean/std, IQR outliers, skew, string length stats, plus duplicate "
        "row count and duplicate-key warnings. Use before running analysis "
        "to spot data issues early."
    )
    parameters = {
        "file": {"type": "string", "required": True,
                 "description": "Workspace filename (e.g. 'data.csv', 'sheet.xlsx')"},
        "max_rows": {"type": "integer", "required": False,
                     "description": "Sample cap (default 200000)"},
        "sample_pct": {"type": "number", "required": False,
                       "description": "Optional sampling percentage 1-100"},
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_PANDAS:
            return {"error": "pandas not available in this environment"}

        fname = (args.get("file") or "").strip()
        if not fname:
            return {"error": "file is required"}

        root = _workspace_root()
        candidate = (root / fname).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return {"error": "file must live inside the workspace"}
        if not candidate.exists():
            return {"error": "file not found: " + fname}

        try:
            max_rows = int(args.get("max_rows") or _MAX_ROWS)
        except (TypeError, ValueError):
            max_rows = _MAX_ROWS
        max_rows = max(100, min(max_rows, _MAX_ROWS))

        try:
            df = _load_df(candidate)
        except Exception as e:
            return {"error": type(e).__name__ + ": " + str(e)[:200]}

        total_rows_raw = len(df)
        if total_rows_raw > max_rows:
            df = df.head(max_rows)
            sampled = True
        else:
            sampled = False

        if df.shape[1] > _MAX_COLS:
            df = df.iloc[:, :_MAX_COLS]

        # Row-level checks
        try:
            dup_rows = int(df.duplicated().sum())
        except Exception:
            dup_rows = 0

        # Duplicate detection on candidate key columns (string cols with
        # high uniqueness — likely IDs)
        dup_key_hints = []
        for c in df.columns:
            s = df[c]
            if df.shape[0] < 2:
                break
            try:
                uniq = s.nunique(dropna=True)
                # Suspicious if it's 60-99% unique (possible ID w/ dups)
                pct = uniq / df.shape[0]
                # Consider any non-float, non-datetime column a candidate key
                is_id_like = (
                    not pd.api.types.is_float_dtype(s)
                    and not pd.api.types.is_datetime64_any_dtype(s)
                )
                if 0.6 <= pct < 0.999 and is_id_like:
                    d = int(df[c].duplicated().sum())
                    if d > 0:
                        dup_key_hints.append({"column": str(c), "dups": d})
            except Exception:
                continue

        col_reports = {}
        for c in df.columns:
            try:
                col_reports[str(c)] = _col_report(df[c])
            except Exception as e:
                col_reports[str(c)] = {"error": type(e).__name__ + ": " + str(e)[:120]}

        return {
            "file": fname,
            "size_bytes": candidate.stat().st_size,
            "total_rows_raw": total_rows_raw,
            "rows_analyzed": int(df.shape[0]),
            "sampled": sampled,
            "columns": int(df.shape[1]),
            "duplicate_rows": dup_rows,
            "duplicate_key_hints": dup_key_hints,
            "column_reports": col_reports,
        }
