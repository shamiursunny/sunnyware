# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Batch financial metrics tool (Part 82).

Computes Sharpe/Sortino/VaR/CVaR/max-drawdown for MULTIPLE return
series in one call. Uses empyrical-reloaded when available, falls back
to numpy implementations otherwise (financial_metrics logic).
"""
from typing import Optional

try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False

try:
    import empyrical as _emp
    _HAS_EMP = True
except Exception:
    _HAS_EMP = False


_MAX_SERIES = 25
_MAX_NAME_LEN = 60


def _numpy_metrics(returns, rf_annual: float, ppy: int) -> dict:
    """Fallback metric computation without empyrical."""
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 2:
        return {"error": "need >= 2 numeric values"}
    rf_period = rf_annual / ppy
    total_return = float(np.prod(1.0 + r) - 1.0)
    mean_r = float(np.mean(r))
    std_r = float(np.std(r, ddof=1))
    annual_return = mean_r * ppy
    annual_vol = std_r * (ppy ** 0.5)
    excess = r - rf_period
    sd = float(np.std(excess, ddof=1))
    sharpe = float(np.mean(excess) / sd * (ppy ** 0.5)) if sd > 0 else 0.0
    downside = excess[excess < 0]
    if downside.size > 1:
        dd = float(np.std(downside, ddof=1))
        sortino = float(np.mean(excess) / dd * (ppy ** 0.5)) if dd > 0 else None
    else:
        sortino = None
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min())
    var_95 = float(np.percentile(r, 5))
    var_99 = float(np.percentile(r, 1))
    tail95 = r[r <= var_95]
    cvar_95 = float(tail95.mean()) if tail95.size else var_95

    # Part 85a: extra ratios
    # Calmar = annualized return / |max drawdown|
    calmar = None
    if max_dd < 0:
        calmar = round(annual_return / abs(max_dd), 4)
    # Omega ratio = sum(gains) / sum(losses), threshold = rf per period
    gains = np.clip(r - rf_period, 0, None)
    losses = -np.clip(r - rf_period, None, 0)
    denom = losses.sum()
    omega = round(float(gains.sum() / denom), 4) if denom > 0 else None
    # Tail ratio = |95th percentile| / |5th percentile|
    q95 = float(np.percentile(r, 95))
    tail_ratio = round(abs(q95) / abs(var_95), 4) if var_95 != 0 else None
    # Downside deviation (annualized)
    down = r[r < rf_period]
    down_dev_annual = None
    if down.size > 1:
        down_dev_annual = round(float(np.std(down, ddof=1)) * (ppy ** 0.5), 6)
    # Upside/downside capture ratio (vs a simple benchmark = mean of r)
    bench_mean = float(np.mean(r))
    up_mask = r > bench_mean
    dn_mask = r < bench_mean
    up_capture = None
    dn_capture = None
    if bench_mean != 0 and up_mask.any():
        up_capture = round(float(r[up_mask].mean() / bench_mean), 4) if bench_mean > 0 else None
    if bench_mean != 0 and dn_mask.any():
        dn_capture = round(float(r[dn_mask].mean() / bench_mean), 4) if bench_mean > 0 else None
    # Win rate
    win_rate = round(float((r > 0).sum()) / r.size, 4) if r.size > 0 else 0.0
    # Profit factor = sum(wins) / |sum(losses)|
    wins_sum = float(r[r > 0].sum())
    losses_sum = abs(float(r[r < 0].sum()))
    profit_factor = round(wins_sum / losses_sum, 4) if losses_sum > 0 else None
    # Skew and kurtosis
    try:
        skew = round(float(np.mean(((r - mean_r) / std_r) ** 3)), 4) if std_r > 0 else None
        kurt = round(float(np.mean(((r - mean_r) / std_r) ** 4)) - 3.0, 4) if std_r > 0 else None
    except Exception:
        skew = None
        kurt = None

    return {
        "total_return": round(total_return, 6),
        "annualized_return": round(annual_return, 6),
        "annualized_volatility": round(annual_vol, 6),
        "downside_deviation_annual": down_dev_annual,
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4) if sortino is not None else None,
        "calmar_ratio": calmar,
        "omega_ratio": omega,
        "tail_ratio": tail_ratio,
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "upside_capture": up_capture,
        "downside_capture": dn_capture,
        "max_drawdown": round(max_dd, 6),
        "var_95": round(var_95, 6),
        "var_99": round(var_99, 6),
        "cvar_95": round(cvar_95, 6),
        "best_period": round(float(np.max(r)), 6),
        "worst_period": round(float(np.min(r)), 6),
        "mean_period_return": round(mean_r, 8),
        "std_period_return": round(std_r, 8),
        "skew": skew,
        "excess_kurtosis": kurt,
        "n_periods": int(r.size),
    }


def _empyrical_metrics(returns, rf_annual: float, ppy: int) -> dict:
    """Compute metrics via empyrical-reloaded."""
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 2:
        return {"error": "need >= 2 numeric values"}

    def _f(x):
        try:
            v = float(x)
            if np.isnan(v) or np.isinf(v):
                return None
            return round(v, 6)
        except Exception:
            return None

    try:
        return {
            "total_return": _f(_emp.cum_returns_final(r)),
            "annualized_return": _f(_emp.annual_return(r, period="daily")
                                    if ppy == 252 else _emp.annual_return(r)),
            "annualized_volatility": _f(_emp.annual_volatility(r, period="daily")
                                        if ppy == 252 else _emp.annual_volatility(r)),
            "sharpe_ratio": _f(_emp.sharpe_ratio(r, risk_free=rf_annual,
                                                 period="daily" if ppy == 252 else "daily")),
            "sortino_ratio": _f(_emp.sortino_ratio(r, required_return=rf_annual,
                                                   period="daily" if ppy == 252 else "daily")),
            "max_drawdown": _f(_emp.max_drawdown(r)),
            "var_95": _f(_emp.value_at_risk(r, cutoff=0.05)),
            "cvar_95": _f(_emp.conditional_value_at_risk(r, cutoff=0.05)),
            "calmar_ratio": _f(_emp.calmar_ratio(r)),
            "omega_ratio": _f(_emp.omega_ratio(r, required_return=rf_annual)),
            "tail_ratio": _f(_emp.tail_ratio(r)),
            "downside_deviation_annual": _f(_emp.downside_risk(r)),
            "best_period": _f(np.max(r)),
            "worst_period": _f(np.min(r)),
            "mean_period_return": _f(np.mean(r)),
            "std_period_return": _f(np.std(r, ddof=1)),
            "n_periods": int(r.size),
            "engine": "empyrical-reloaded",
        }
    except Exception as e:
        # Fall back silently
        out = _numpy_metrics(returns, rf_annual, ppy)
        out["empyrical_error"] = type(e).__name__ + ": " + str(e)[:120]
        return out


class MetricsBatchTool:
    name = "metrics_batch"
    description = (
        "Compute 20+ metrics (Sharpe, Sortino, Calmar, Omega, tail ratio, "
        "profit factor, win rate, downside deviation, capture ratios, "
        "skew, kurtosis, max drawdown, VaR, CVaR, annualized return/vol) "
        "for MULTIPLE return series in one call. "
        "Each series is a {name, returns: [...]}. Returns per-series "
        "metrics + a comparison summary (best Sharpe, worst drawdown, "
        "etc.). Uses empyrical-reloaded when available; falls back to "
        "numpy. Max 25 series per call."
    )
    parameters = {
        "series": {
            "type": "array",
            "required": True,
            "description": (
                "Array of {name: str, returns: [floats]}. "
                "Max 25 series. Each series needs >= 2 numeric values."
            ),
        },
        "periods_per_year": {
            "type": "integer",
            "required": False,
            "description": "Periods per year: 252 trading days (default), 12 months, 4 quarters",
        },
        "risk_free_rate": {
            "type": "number",
            "required": False,
            "description": "Annual risk-free rate (default 0.02)",
        },
    }

    async def run(self, args: dict) -> dict:
        if not _HAS_NUMPY:
            return {"error": "numpy not available"}
        series = args.get("series")
        if not isinstance(series, list) or not series:
            return {"error": "series must be a non-empty array"}
        if len(series) > _MAX_SERIES:
            return {"error": "too many series (max " + str(_MAX_SERIES) + ")"}

        try:
            ppy = int(args.get("periods_per_year") or 252)
        except (TypeError, ValueError):
            ppy = 252
        ppy = max(1, min(ppy, 365))

        try:
            rf = float(args.get("risk_free_rate") or 0.02)
        except (TypeError, ValueError):
            rf = 0.02

        out = []
        for i, spec in enumerate(series):
            if not isinstance(spec, dict):
                out.append({"index": i, "error": "entry must be an object"})
                continue
            name = str(spec.get("name") or ("series_" + str(i)))[:_MAX_NAME_LEN]
            rets = spec.get("returns")
            if not isinstance(rets, list) or len(rets) < 2:
                out.append({"name": name, "error": "returns must be an array of >= 2 numbers"})
                continue
            try:
                # Try to coerce values
                clean = []
                for v in rets:
                    try:
                        clean.append(float(v))
                    except (TypeError, ValueError):
                        continue
                if len(clean) < 2:
                    out.append({"name": name, "error": "not enough numeric values"})
                    continue
            except Exception as e:
                out.append({"name": name, "error": type(e).__name__ + ": " + str(e)[:120]})
                continue

            if _HAS_EMP:
                metrics = _empyrical_metrics(clean, rf, ppy)
            else:
                metrics = _numpy_metrics(clean, rf, ppy)
                metrics["engine"] = "numpy-fallback"
            out.append({"name": name, **metrics})

        # Summary across series (only successful ones)
        ok = [r for r in out if "sharpe_ratio" in r and r.get("sharpe_ratio") is not None]
        summary = {}
        if ok:
            try:
                sharpe_sorted = sorted(ok, key=lambda x: x["sharpe_ratio"], reverse=True)
                summary["best_sharpe"] = {"name": sharpe_sorted[0]["name"],
                                          "value": sharpe_sorted[0]["sharpe_ratio"]}
                summary["worst_sharpe"] = {"name": sharpe_sorted[-1]["name"],
                                           "value": sharpe_sorted[-1]["sharpe_ratio"]}
            except Exception:
                pass
            try:
                dd_sorted = sorted(ok, key=lambda x: x.get("max_drawdown") or 0)
                summary["worst_drawdown"] = {"name": dd_sorted[0]["name"],
                                             "value": dd_sorted[0].get("max_drawdown")}
                summary["best_drawdown"] = {"name": dd_sorted[-1]["name"],
                                            "value": dd_sorted[-1].get("max_drawdown")}
            except Exception:
                pass

        return {
            "periods_per_year": ppy,
            "risk_free_rate_annual": rf,
            "engine": "empyrical-reloaded" if _HAS_EMP else "numpy-fallback",
            "series_count": len(out),
            "ok_count": len(ok),
            "summary": summary,
            "results": out,
        }
