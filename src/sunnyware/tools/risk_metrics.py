# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 130: deterministic portfolio risk metrics.

Pure Python + numpy/scipy. No LLM, no network. Provides VaR, CVaR,
volatility, Sharpe, Sortino, Calmar, max drawdown, stress testing,
correlation, and beta. Designed for the risk_ins and quant roles.

All metrics state their methodology in the output so downstream
consumers know the assumptions.
"""
import json
import math

try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False

try:
    from scipy.stats import norm as _norm
    _HAS_SCIPY = True
except Exception:
    _HAS_SCIPY = False


DEFAULT_PERIODS_PER_YEAR = 252
DEFAULT_MC_PATHS = 10000


def _to_array(value, name="value"):
    """Accept JSON string or list. Return list of floats."""
    if value is None:
        raise ValueError(name + " is required")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception as e:
            raise ValueError(name + " is not valid JSON: " + str(e))
    if not isinstance(value, (list, tuple)):
        raise ValueError(name + " must be a list of numbers")
    out = []
    for i, v in enumerate(value):
        try:
            fv = float(v)
        except Exception:
            raise ValueError(name + "[" + str(i) + "] is not a number")
        if math.isnan(fv) or math.isinf(fv):
            raise ValueError(name + "[" + str(i) + "] is NaN or Inf")
        out.append(fv)
    return out


def returns_from_prices(prices):
    """Convert a price series to simple arithmetic returns."""
    if len(prices) < 2:
        return []
    return [(prices[i] - prices[i-1]) / prices[i-1]
            for i in range(1, len(prices))]


def _mean(xs):
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def _std(xs, sample=True):
    if not xs or len(xs) == 1:
        return 0.0
    m = _mean(xs)
    s = sum((x - m) ** 2 for x in xs)
    denom = (len(xs) - 1) if sample else len(xs)
    return math.sqrt(s / denom) if denom > 0 else 0.0


def _quantile(xs, q):
    if not xs:
        raise ValueError("cannot compute quantile of empty list")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def var_historical(returns, confidence=0.95):
    """Historical-simulation VaR. Returns loss magnitude as positive number."""
    if not returns:
        raise ValueError("returns is empty")
    threshold = _quantile(returns, 1.0 - confidence)
    return {
        "methodology": "historical simulation",
        "confidence": confidence,
        "var_loss": -threshold,
        "var_return": threshold,
        "n_observations": len(returns),
    }


def var_parametric(returns, confidence=0.95):
    """Parametric (normal) VaR."""
    if len(returns) < 2:
        raise ValueError("parametric VaR needs >= 2 returns")
    if not _HAS_SCIPY:
        raise ValueError("scipy not available for parametric VaR")
    mu = _mean(returns)
    sigma = _std(returns)
    z = _norm.ppf(1.0 - confidence)
    threshold = mu + z * sigma
    return {
        "methodology": "parametric (normal)",
        "confidence": confidence,
        "mean": mu,
        "std": sigma,
        "z_score": float(z),
        "var_loss": -threshold,
        "var_return": threshold,
    }


def var_monte_carlo(returns, confidence=0.95, n_paths=DEFAULT_MC_PATHS,
                    seed=42):
    """Monte Carlo VaR via bootstrap resampling."""
    if len(returns) < 2:
        raise ValueError("Monte Carlo VaR needs >= 2 returns")
    if not _HAS_NUMPY:
        raise ValueError("numpy not available for Monte Carlo VaR")
    rng = np.random.default_rng(seed)
    arr = np.asarray(returns, dtype=float)
    samples = rng.choice(arr, size=n_paths, replace=True)
    threshold = float(np.quantile(samples, 1.0 - confidence))
    return {
        "methodology": "monte carlo (bootstrap)",
        "confidence": confidence,
        "n_paths": n_paths,
        "seed": seed,
        "var_loss": -threshold,
        "var_return": threshold,
    }


def cvar_historical(returns, confidence=0.95):
    """Expected Shortfall (CVaR): mean loss in the tail beyond VaR."""
    if not returns:
        raise ValueError("returns is empty")
    threshold = _quantile(returns, 1.0 - confidence)
    tail = [r for r in returns if r <= threshold]
    if not tail:
        tail = [threshold]
    es = _mean(tail)
    return {
        "methodology": "historical ES (mean of tail beyond VaR)",
        "confidence": confidence,
        "var_return": threshold,
        "cvar_loss": -es,
        "cvar_return": es,
        "tail_observations": len(tail),
    }


def sharpe_ratio(returns, risk_free=0.0, periods_per_year=DEFAULT_PERIODS_PER_YEAR):
    """Annualized Sharpe ratio (arithmetic approximation)."""
    if len(returns) < 2:
        raise ValueError("Sharpe needs >= 2 returns")
    mu = _mean(returns) - risk_free
    sigma = _std(returns)
    if sigma == 0:
        return {"methodology": "arithmetic annualization",
                "sharpe": None, "note": "zero volatility"}
    return {
        "methodology": "arithmetic annualization",
        "risk_free_per_period": risk_free,
        "periods_per_year": periods_per_year,
        "mean_excess_return": mu,
        "std": sigma,
        "sharpe": (mu / sigma) * math.sqrt(periods_per_year),
    }


def sortino_ratio(returns, risk_free=0.0, periods_per_year=DEFAULT_PERIODS_PER_YEAR):
    """Annualized Sortino ratio (downside deviation only)."""
    if len(returns) < 2:
        raise ValueError("Sortino needs >= 2 returns")
    mu = _mean(returns) - risk_free
    downside = [min(0.0, r - risk_free) for r in returns]
    dd = math.sqrt(sum(d * d for d in downside) / len(downside))
    if dd == 0:
        return {"methodology": "downside deviation",
                "sortino": None, "note": "no downside deviation"}
    return {
        "methodology": "downside deviation",
        "risk_free_per_period": risk_free,
        "periods_per_year": periods_per_year,
        "downside_deviation": dd,
        "sortino": (mu / dd) * math.sqrt(periods_per_year),
    }


def max_drawdown(returns):
    """Maximum peak-to-trough drawdown of compounded equity curve."""
    if not returns:
        raise ValueError("returns is empty")
    equity = [1.0]
    for r in returns:
        equity.append(equity[-1] * (1.0 + r))
    peak = equity[0]
    max_dd = 0.0
    peak_idx = 0
    max_peak_idx = 0
    max_trough_idx = 0
    for i, v in enumerate(equity):
        if v > peak:
            peak = v
            peak_idx = i
        dd = (v - peak) / peak if peak != 0 else 0.0
        if dd < max_dd:
            max_dd = dd
            max_peak_idx = peak_idx
            max_trough_idx = i
    return {
        "methodology": "peak-to-trough on compounded equity",
        "max_drawdown": max_dd,
        "max_drawdown_pct": abs(max_dd) * 100.0,
        "peak_index": max_peak_idx,
        "trough_index": max_trough_idx,
        "observations": len(returns),
    }


def calmar_ratio(returns, periods_per_year=DEFAULT_PERIODS_PER_YEAR):
    """Calmar ratio: annualized return / |max drawdown|."""
    if len(returns) < 2:
        raise ValueError("Calmar needs >= 2 returns")
    mean = _mean(returns)
    try:
        ann_ret = (1.0 + mean) ** periods_per_year - 1.0
    except Exception:
        ann_ret = mean * periods_per_year
    dd = max_drawdown(returns)
    mdd = abs(dd["max_drawdown"])
    if mdd == 0:
        return {"methodology": "annualized return / max drawdown",
                "calmar": None, "note": "no drawdown"}
    return {
        "methodology": "annualized return / max drawdown",
        "annualized_return": ann_ret,
        "max_drawdown": dd["max_drawdown"],
        "calmar": ann_ret / mdd,
    }


def annualized_volatility(returns, periods_per_year=DEFAULT_PERIODS_PER_YEAR):
    """Annualized standard deviation."""
    sigma = _std(returns)
    return {
        "methodology": "sample std * sqrt(periods_per_year)",
        "periods_per_year": periods_per_year,
        "per_period_std": sigma,
        "annualized_volatility": sigma * math.sqrt(periods_per_year),
    }


def stress_test(returns, shocks):
    """Apply each shock as an instantaneous return; recompute VaR/CVaR."""
    if not returns:
        raise ValueError("returns is empty")
    if not shocks:
        raise ValueError("shocks is empty")
    base_var = var_historical(returns, 0.95)["var_loss"]
    results = []
    for shock in shocks:
        stressed = list(returns) + [float(shock)]
        try:
            v = var_historical(stressed, 0.95)
            c = cvar_historical(stressed, 0.95)
            results.append({
                "shock": float(shock),
                "stressed_var_95": v["var_loss"],
                "stressed_cvar_95": c["cvar_loss"],
                "delta_var": v["var_loss"] - base_var,
                "n_observations": len(stressed),
            })
        except Exception as e:
            results.append({"shock": float(shock), "error": str(e)})
    return {
        "methodology": "append each shock to return series, recompute VaR/CVaR",
        "base_var_95": base_var,
        "scenarios": results,
    }


def correlation_matrix(return_series):
    """Pairwise Pearson correlation across multiple return series."""
    if not _HAS_NUMPY:
        raise ValueError("numpy not available")
    names = list(return_series.keys())
    if len(names) < 2:
        raise ValueError("need >= 2 series for correlation")
    min_len = min(len(return_series[n]) for n in names)
    if min_len < 2:
        raise ValueError("all series must have >= 2 returns")
    matrix = np.zeros((len(names), len(names)))
    for i, ni in enumerate(names):
        a = np.asarray(return_series[ni][:min_len], dtype=float)
        for j, nj in enumerate(names):
            b = np.asarray(return_series[nj][:min_len], dtype=float)
            if a.std() == 0 or b.std() == 0:
                matrix[i, j] = 0.0
            else:
                matrix[i, j] = float(np.corrcoef(a, b)[0, 1])
    return {
        "methodology": "Pearson correlation, truncated to min length",
        "names": names,
        "truncated_length": min_len,
        "matrix": matrix.tolist(),
    }


def beta_metric(returns, benchmark_returns):
    """Beta of asset vs benchmark (OLS slope)."""
    n = min(len(returns), len(benchmark_returns))
    returns = returns[:n]
    benchmark_returns = benchmark_returns[:n]
    if len(returns) < 2:
        raise ValueError("beta needs >= 2 aligned returns")
    ma = _mean(returns)
    mb = _mean(benchmark_returns)
    cov = sum((a - ma) * (b - mb)
              for a, b in zip(returns, benchmark_returns))
    var_b = sum((b - mb) ** 2 for b in benchmark_returns)
    if var_b == 0:
        return {"methodology": "OLS slope",
                "beta": None, "note": "benchmark variance is zero"}
    b = cov / var_b
    sa = _std(returns)
    sb = _std(benchmark_returns)
    corr = (cov / (len(returns) - 1)) / (sa * sb) if sa * sb > 0 else 0.0
    return {
        "methodology": "OLS slope of asset returns vs benchmark",
        "n_observations": len(returns),
        "beta": b,
        "correlation": corr,
        "r_squared": corr * corr,
    }


def full_summary(returns, confidence=0.95,
                 periods_per_year=DEFAULT_PERIODS_PER_YEAR):
    """Aggregate summary with all key metrics."""
    if not returns:
        raise ValueError("returns is empty")
    out = {
        "methodology": "aggregate summary",
        "n_observations": len(returns),
        "mean_return": _mean(returns),
        "std_return": _std(returns),
    }
    for k, fn in [
        ("annualized_volatility", lambda: annualized_volatility(returns, periods_per_year)),
        ("var_historical_95", lambda: var_historical(returns, 0.95)),
        ("var_parametric_95", lambda: var_parametric(returns, 0.95)),
        ("cvar_historical_95", lambda: cvar_historical(returns, 0.95)),
        ("sharpe", lambda: sharpe_ratio(returns, periods_per_year=periods_per_year)),
        ("sortino", lambda: sortino_ratio(returns, periods_per_year=periods_per_year)),
        ("max_drawdown", lambda: max_drawdown(returns)),
        ("calmar", lambda: calmar_ratio(returns, periods_per_year=periods_per_year)),
    ]:
        try:
            out[k] = fn()
        except Exception as e:
            out[k + "_error"] = str(e)
    return out


_ACTIONS = ["summary", "var", "cvar", "volatility", "sharpe", "sortino",
            "drawdown", "calmar", "stress_test", "correlation", "beta",
            "from_prices"]


class RiskMetricsTool:
    name = "risk_metrics"
    description = (
        "Deterministic portfolio risk metrics: VaR (historical/parametric/"
        "Monte Carlo), CVaR/Expected Shortfall, annualized volatility, "
        "Sharpe, Sortino, Calmar, max drawdown, stress testing, correlation, "
        "and beta. Pure Python (numpy/scipy) - no LLM, no network. Every "
        "result reports its methodology and assumptions. Use for investment "
        "risk, credit risk, and structured product analysis."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "One of: summary, var, cvar, volatility, sharpe, sortino, drawdown, calmar, stress_test, correlation, beta, from_prices",
            "required": True,
        },
        "returns": {
            "type": "string",
            "description": "JSON array of per-period returns, e.g. '[0.01,-0.02]'",
            "required": False,
        },
        "prices": {
            "type": "string",
            "description": "JSON array of prices (for action=from_prices)",
            "required": False,
        },
        "benchmark_returns": {
            "type": "string",
            "description": "JSON array of benchmark returns (for action=beta)",
            "required": False,
        },
        "series": {
            "type": "string",
            "description": "JSON object of {name: [returns]} (for action=correlation)",
            "required": False,
        },
        "shocks": {
            "type": "string",
            "description": "JSON array of return shocks (for action=stress_test)",
            "required": False,
        },
        "confidence": {
            "type": "number",
            "description": "VaR/CVaR confidence level (default 0.95)",
            "required": False,
        },
        "periods_per_year": {
            "type": "integer",
            "description": "Annualization factor (default 252)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = (args.get("action") or "").strip().lower()
        if not action:
            return {"error": "action is required", "available": _ACTIONS}

        try:
            conf = float(args.get("confidence") or 0.95)
        except Exception:
            return {"error": "confidence must be a number"}
        if not (0.5 < conf < 1.0):
            return {"error": "confidence must be between 0.5 and 1.0"}

        try:
            ppy = int(args.get("periods_per_year") or DEFAULT_PERIODS_PER_YEAR)
        except Exception:
            ppy = DEFAULT_PERIODS_PER_YEAR

        try:
            if action == "from_prices":
                p = _to_array(args.get("prices"), "prices")
                r = returns_from_prices(p)
                if not r:
                    return {"error": "need >= 2 prices"}
                return {"returns": r, "n": len(r),
                        "methodology": "simple arithmetic returns"}

            if action == "summary":
                return full_summary(_to_array(args.get("returns"), "returns"),
                                    confidence=conf, periods_per_year=ppy)

            if action == "var":
                r = _to_array(args.get("returns"), "returns")
                out = {}
                for name, fn in [
                    ("historical", lambda: var_historical(r, conf)),
                    ("parametric", lambda: var_parametric(r, conf)),
                    ("monte_carlo", lambda: var_monte_carlo(r, conf)),
                ]:
                    try:
                        out[name] = fn()
                    except Exception as e:
                        out[name + "_error"] = str(e)
                return out

            if action == "cvar":
                return cvar_historical(
                    _to_array(args.get("returns"), "returns"), conf)

            if action == "volatility":
                return annualized_volatility(
                    _to_array(args.get("returns"), "returns"), ppy)

            if action == "sharpe":
                return sharpe_ratio(
                    _to_array(args.get("returns"), "returns"),
                    periods_per_year=ppy)

            if action == "sortino":
                return sortino_ratio(
                    _to_array(args.get("returns"), "returns"),
                    periods_per_year=ppy)

            if action == "drawdown":
                return max_drawdown(_to_array(args.get("returns"), "returns"))

            if action == "calmar":
                return calmar_ratio(
                    _to_array(args.get("returns"), "returns"),
                    periods_per_year=ppy)

            if action == "stress_test":
                return stress_test(
                    _to_array(args.get("returns"), "returns"),
                    _to_array(args.get("shocks"), "shocks"))

            if action == "correlation":
                raw = args.get("series")
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except Exception as e:
                        return {"error": "series is not valid JSON: " + str(e)}
                if not isinstance(raw, dict):
                    return {"error": "series must be a JSON object of {name: [returns]}"}
                clean = {}
                for k, v in raw.items():
                    clean[str(k)] = _to_array(v, "series[" + str(k) + "]")
                return correlation_matrix(clean)

            if action == "beta":
                return beta_metric(
                    _to_array(args.get("returns"), "returns"),
                    _to_array(args.get("benchmark_returns"), "benchmark_returns"))

            return {"error": "unknown action '" + action + "'",
                    "available": _ACTIONS}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": type(e).__name__ + ": " + str(e)}
