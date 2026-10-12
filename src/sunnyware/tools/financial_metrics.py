# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Financial risk + performance metrics (Part 55).

Computes the standard FP&A / quant stack from a return or price series:
Sharpe, Sortino, max drawdown, VaR, CVaR, annualized return/volatility.
Pure numpy — no extra dependencies.
"""
import csv
import os
from pathlib import Path
from typing import Optional

import numpy as np


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _prices_to_returns(prices):
    arr = np.asarray(prices, dtype=float)
    if arr.size < 2:
        return None
    prev = arr[:-1]
    prev_safe = np.where(prev == 0, np.nan, prev)
    rets = np.diff(arr) / prev_safe
    return rets[~np.isnan(rets)]


def _load_series(args: dict) -> tuple:
    """Return (returns_array, source_label, error)."""
    returns = args.get("returns")
    prices = args.get("prices")

    if isinstance(returns, list) and len(returns) >= 2:
        try:
            arr = np.asarray([float(x) for x in returns], dtype=float)
        except (TypeError, ValueError) as e:
            return None, None, f"non-numeric value in returns: {e}"
        return arr, "returns (inline)", None

    if isinstance(prices, list) and len(prices) >= 2:
        arr = _prices_to_returns(prices)
        if arr is None or arr.size < 2:
            return None, None, "prices must have >= 2 values"
        return arr, "prices (inline)", None

    fname = (args.get("file") or "").strip()
    column = (args.get("column") or "").strip()
    if not fname or not column:
        return None, None, "provide either 'returns'/'prices', or 'file' + 'column'"

    root = _workspace_root()
    candidate = (root / fname).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, None, "file must live inside the workspace"
    if not candidate.exists():
        return None, None, f"file not found: {fname}"
    if candidate.suffix.lower() not in (".csv", ".tsv"):
        return None, None, "only .csv or .tsv supported for file input"

    delim = "\t" if candidate.suffix.lower() == ".tsv" else ","
    values = []
    try:
        with candidate.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=delim)
            for row in reader:
                v = row.get(column)
                if v is None:
                    return None, None, f"column '{column}' not found"
                try:
                    values.append(float(v))
                except (TypeError, ValueError):
                    continue
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"

    if len(values) < 2:
        return None, None, f"need >= 2 numeric values in column '{column}'"

    # Heuristic: if all values are positive and clearly trending away from 1.0,
    # treat as prices; otherwise treat as returns.
    arr = np.asarray(values, dtype=float)
    if np.all(arr > 0) and (np.abs(arr).mean() > 0.5):
        rets = _prices_to_returns(arr)
        return (rets, f"prices from {fname}[{column}]", None) if rets is not None \
            else (None, None, "could not convert prices to returns")
    return arr, f"returns from {fname}[{column}]", None


class FinancialMetricsTool:
    name = "financial_metrics"
    description = (
        "Compute standard financial risk + performance metrics from a return "
        "or price series: total/annualized return, volatility, Sharpe, Sortino, "
        "max drawdown, historical VaR and CVaR at 95%, best/worst period. "
        "Provide EITHER 'returns' (period returns) OR 'prices' (price series) "
        "as arrays, OR 'file' + 'column' for a workspace CSV/TSV."
    )
    parameters = {
        "returns": {
            "type": "array",
            "description": "Period returns (e.g. daily) as an array of floats",
            "required": False,
        },
        "prices": {
            "type": "array",
            "description": "Price series; converted to returns internally",
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
        "risk_free_rate": {
            "type": "number",
            "description": "Annual risk-free rate (default 0.02 = 2%)",
            "required": False,
        },
        "periods_per_year": {
            "type": "integer",
            "description": "Periods per year: 252 trading days, 12 months, 4 quarters (default 252)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        returns, label, err = _load_series(args)
        if err:
            return {"error": err}
        if returns is None or returns.size < 2:
            return {"error": "not enough data points for metrics"}

        try:
            rf_annual = float(args.get("risk_free_rate", 0.02))
        except (TypeError, ValueError):
            return {"error": "risk_free_rate must be a number"}
        try:
            ppy = int(args.get("periods_per_year", 252))
        except (TypeError, ValueError):
            return {"error": "periods_per_year must be an integer"}
        ppy = max(1, min(ppy, 365))

        rf_period = rf_annual / ppy

        # Compound total return
        total_return = float(np.prod(1.0 + returns) - 1.0)
        n = returns.size
        # Annualized arithmetic return + vol (standard quant conventions)
        mean_r = float(np.mean(returns))
        std_r = float(np.std(returns, ddof=1)) if n > 1 else 0.0
        annual_return = mean_r * ppy
        annual_vol = std_r * (ppy ** 0.5)

        # Sharpe
        excess = returns - rf_period
        sharpe = float(np.mean(excess) / np.std(excess, ddof=1) * (ppy ** 0.5)) \
            if np.std(excess, ddof=1) > 0 else 0.0

        # Sortino (downside deviation)
        downside = excess[excess < 0]
        if downside.size > 0:
            dd = float(np.std(downside, ddof=1)) if downside.size > 1 else 0.0
            sortino = float(np.mean(excess) / dd * (ppy ** 0.5)) if dd > 0 else 0.0
        else:
            sortino = None  # undefined when no negative returns

        # Max drawdown from cumulative equity curve
        equity = np.cumprod(1.0 + returns)
        peak = np.maximum.accumulate(equity)
        dd_series = (equity - peak) / peak
        max_dd = float(dd_series.min())
        # Peak/trough positions
        trough_idx = int(np.argmin(dd_series))
        peak_idx = int(np.argmax(equity[:trough_idx + 1])) if trough_idx > 0 else 0

        # Historical VaR / CVaR at 95%
        var_95 = float(np.percentile(returns, 5))
        tail = returns[returns <= var_95]
        cvar_95 = float(tail.mean()) if tail.size > 0 else var_95

        # Best / worst period
        best = float(np.max(returns))
        worst = float(np.min(returns))

        # Calmar = annual return / |max_dd|
        calmar = float(annual_return / abs(max_dd)) if max_dd < 0 else None

        return {
            "source": label,
            "n_periods": int(n),
            "periods_per_year": ppy,
            "risk_free_rate_annual": rf_annual,
            "returns_summary": {
                "total_return": round(total_return, 6),
                "annualized_return": round(annual_return, 6),
                "annualized_volatility": round(annual_vol, 6),
                "best_period": round(best, 6),
                "worst_period": round(worst, 6),
                "mean_period_return": round(mean_r, 8),
                "std_period_return": round(std_r, 8),
            },
            "risk_adjusted": {
                "sharpe_ratio": round(sharpe, 4),
                "sortino_ratio": round(sortino, 4) if sortino is not None else None,
                "calmar_ratio": round(calmar, 4) if calmar is not None else None,
            },
            "drawdown": {
                "max_drawdown": round(max_dd, 6),
                "peak_index": peak_idx,
                "trough_index": trough_idx,
            },
            "tail_risk": {
                "var_95_historical": round(var_95, 6),
                "cvar_95_historical": round(cvar_95, 6),
                "var_99_historical": round(float(np.percentile(returns, 1)), 6),
            },
        }
