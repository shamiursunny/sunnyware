# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""ARIMA time-series forecasting tool (Part 53).

Fits an ARIMA model to a numeric series and forecasts N periods ahead.
Auto-selects order via AIC across a small grid if order not provided.
Returns numbers only — pipe result into chart_from_data to visualize.
"""
import csv
import os
from pathlib import Path
from typing import Optional

try:
    from statsmodels.tsa.arima.model import ARIMA  # type: ignore
    import warnings as _warnings
    _HAS_SM = True
except Exception:
    _HAS_SM = False


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _load_series(args: dict) -> tuple:
    """Return (list_of_floats, error)."""
    data = args.get("data")
    if isinstance(data, list) and data:
        series = []
        for v in data:
            try:
                series.append(float(v))
            except (TypeError, ValueError):
                return None, f"non-numeric value in data: {v!r}"
        if len(series) < 4:
            return None, "need at least 4 data points"
        return series, None

    fname = (args.get("file") or "").strip()
    if not fname:
        return None, "provide either 'data' or 'file'"

    column = (args.get("column") or "").strip()
    if not column:
        return None, "when using 'file', you must specify 'column'"

    root = _workspace_root()
    candidate = (root / fname).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, "file must live inside the workspace"
    if not candidate.exists():
        return None, f"file not found: {fname}"
    if candidate.suffix.lower() not in (".csv", ".tsv"):
        return None, "only .csv or .tsv supported for file input"

    delim = "\t" if candidate.suffix.lower() == ".tsv" else ","
    series = []
    try:
        with candidate.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                v = row.get(column)
                if v is None:
                    return None, f"column '{column}' not found"
                try:
                    series.append(float(v))
                except (TypeError, ValueError):
                    continue
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

    if len(series) < 4:
        return None, f"need at least 4 numeric values in column '{column}'"
    return series, None


def _auto_order(series) -> tuple:
    """Pick (p,d,q) via AIC over a small grid. Returns (order, aic)."""
    best = None
    best_aic = float("inf")
    for p in (0, 1, 2):
        for d in (0, 1):
            for q in (0, 1, 2):
                try:
                    with _warnings.catch_warnings():
                        _warnings.simplefilter("ignore")
                        m = ARIMA(series, order=(p, d, q)).fit()
                    if m.aic < best_aic:
                        best_aic = m.aic
                        best = (p, d, q)
                except Exception:
                    continue
    return best, best_aic


class ForecastArimaTool:
    name = "forecast_arima"
    description = (
        "Fit an ARIMA model to a numeric time series and forecast N periods "
        "ahead. Provide EITHER 'data' (array of numbers) OR 'file' + "
        "'column'. Auto-selects order via AIC if 'order' not given. Returns "
        "forecast values, order, AIC, and in-sample RMSE. Chain the result "
        "into chart_from_data for visualization."
    )
    parameters = {
        "data": {
            "type": "array",
            "description": "Numeric series (>=4 values)",
            "required": False,
        },
        "file": {
            "type": "string",
            "description": "Workspace CSV/TSV file name",
            "required": False,
        },
        "column": {
            "type": "string",
            "description": "Column name (required with 'file')",
            "required": False,
        },
        "periods": {
            "type": "integer",
            "description": "How many periods to forecast (default 6, max 60)",
            "required": False,
        },
        "order": {
            "type": "array",
            "description": "Explicit (p,d,q) tuple. Omit to auto-select via AIC.",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_SM:
            return {"error": "statsmodels not installed in this environment"}

        series, err = _load_series(args)
        if err:
            return {"error": err}

        try:
            periods = int(args.get("periods") or 6)
        except (TypeError, ValueError):
            return {"error": "periods must be an integer"}
        periods = max(1, min(periods, 60))

        order_arg = args.get("order")
        if order_arg:
            try:
                order = tuple(int(x) for x in order_arg)
                if len(order) != 3:
                    return {"error": "order must be [p, d, q]"}
            except (TypeError, ValueError):
                return {"error": "order must be [p, d, q]"}
            auto = False
        else:
            order, _ = _auto_order(series)
            if order is None:
                return {"error": "could not fit any ARIMA order to this series"}
            auto = True

        try:
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore")
                model = ARIMA(series, order=order).fit()
        except Exception as e:
            return {"error": f"fit failed: {type(e).__name__}: {e}"}

        try:
            fc = model.forecast(steps=periods)
            forecast = [float(x) for x in fc]
        except Exception as e:
            return {"error": f"forecast failed: {type(e).__name__}: {e}"}

        # In-sample RMSE as rough quality metric
        try:
            fitted = model.fittedvalues
            resid = [series[i] - float(fitted[i]) for i in range(len(series))]
            rmse = (sum(r * r for r in resid) / len(resid)) ** 0.5
        except Exception:
            rmse = None

        return {
            "order": list(order),
            "auto_selected": auto,
            "aic": round(float(model.aic), 3),
            "periods": periods,
            "n_obs": len(series),
            "forecast": forecast,
            "rmse_in_sample": round(rmse, 4) if rmse is not None else None,
            "last_value": series[-1],
            "note": (
                "Pipe the 'forecast' array into chart_from_data to visualize, "
                "or continue reasoning on the numbers."
            ),
        }
