# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Role personas - curated tool subsets + system prompt addons.

Part 112: subsetting the tool schema per role saves ~4-6K tokens per
request and improves tool-selection accuracy by removing distractors.

Each role has:
  label         - human-readable name (for UI)
  icon          - single emoji
  prompt_addon  - prepended to the base system prompt (may be empty)
  tool_prefixes - tool names starting with any of these are included
  extra_tools   - exact tool names always included
  tools         - explicit override: None = all tools
"""

from . import tools as tools_registry


ROLES = {
    "general": {
        "label": "General",
        "icon": "\u2728",
        "prompt_addon": "",
        "tool_prefixes": None,   # None + tools None -> all tools
        "extra_tools": None,
        "tools": None,
    },

    "fpa": {
        "label": "FP&A Analyst",
        "icon": "\U0001F4CA",
        "prompt_addon": (
            "You are operating in FP&A Analyst mode. Focus on financial "
            "statements, ratios, budgeting, forecasting, and variance "
            "analysis. Prefer edgar_* for SEC filings, fmp_* for structured "
            "financial statements and ratios, fred_* for macro series, and "
            "eulerpool_bonds_* for credit-market context. When asked to "
            "build a model or projection, use python_eval with pandas/numpy "
            "and return a clean table with assumptions called out."
        ),
        "tool_prefixes": ["edgar_", "fmp_", "fred_", "eulerpool_bonds_"],
        "extra_tools": [
            "python_eval", "sql_sandbox_execute", "duckdb_query",
            "read_file", "write_file", "list_files", "rag_search",
            "calculator", "web_search", "echo",
        ],
        "tools": None,
    },

    "quant": {
        "label": "Quant Researcher",
        "icon": "\U0001F9EE",
        "prompt_addon": (
            "You are operating in Quant Researcher mode. Focus on time "
            "series, returns, volatility, backtesting, and derivatives. "
            "Prefer tiingo_* for daily price history, twelvedata_* for "
            "intraday/multi-asset, eulerpool_options_* for option chains "
            "and Greeks, eulerpool_alt_* for alternative data, and fred_* "
            "for macro factors. Use python_eval with numpy/scipy/statsmodels "
            "for regressions, factor models, and simulations. Show your math."
        ),
        "tool_prefixes": [
            "tiingo_", "twelvedata_", "eulerpool_options_",
            "eulerpool_alt_", "eulerpool_stocks_", "fred_", "finnhub_",
        ],
        "extra_tools": [
            "python_eval", "sql_sandbox_execute", "duckdb_query",
            "read_file", "write_file", "list_files", "rag_search",
            "calculator", "web_search",
        ],
        "tools": None,
    },

    "actuary": {
        "label": "Actuarial Analyst",
        "icon": "\U0001F3E6",
        "prompt_addon": (
            "You are operating in Actuarial Analyst mode. Focus on loss "
            "reserving (IBNR), life/pension cashflow projections, and "
            "solvency capital. Use python_eval with:\n"
            "  - chainladder for P&C loss triangles, Chain Ladder, "
            "Bornhuetter-Ferguson, Mack, bootstrap\n"
            "  - lifelib for life/pension model projections\n"
            "  - solvency2_data for EIOPA risk-free rate term structures\n"
            "  - numpy/pandas/scipy/statsmodels for supporting analysis\n"
            "Prefer edgar_* for insurance company financials and fred_* for "
            "macro inputs (rates, inflation). Always state assumptions: "
            "LDF selection, tail factor, discount rate. Verify your numbers."
        ),
        "tool_prefixes": ["edgar_", "fred_"],
        "extra_tools": [
            "python_eval", "sql_sandbox_execute", "duckdb_query",
            "read_file", "write_file", "list_files", "rag_search",
            "calculator", "web_search",
        ],
        "tools": None,
    },

    "tax": {
        "label": "Tax Accountant",
        "icon": "\U0001F9FE",
        "prompt_addon": (
            "You are operating in Tax Accountant mode. Focus on tax "
            "compliance, filing status, deductions, credits, and "
            "cross-jurisdictional considerations. Prefer edgar_* for public "
            "company filings, eulerpool_insider_* for Form 4 / ownership, "
            "fred_* for rate/inflation adjustments, and python_eval with "
            "pandas for ledger/trial-balance work. Always state the tax "
            "year and jurisdiction. Flag when professional counsel is "
            "required."
        ),
        "tool_prefixes": ["edgar_", "fred_", "eulerpool_insider_"],
        "extra_tools": [
            "python_eval", "sql_sandbox_execute", "duckdb_query",
            "read_file", "write_file", "list_files", "rag_search",
            "calculator", "web_search",
        ],
        "tools": None,
    },
}


DEFAULT_ROLE = "general"

_ALIASES = {
    "fp&a": "fpa", "fpa": "fpa", "financial": "fpa",
    "quant": "quant", "quantitative": "quant",
    "actuary": "actuary", "actuarial": "actuary",
    "tax": "tax", "accountant": "tax",
    "general": "general", "default": "general",
}


def _canonical(name):
    if not name:
        return None
    key = str(name).strip().lower()
    return _ALIASES.get(key, key)


# Part 113A: public alias so external modules don't touch a private name
canonical = _canonical


def get_role(name):
    """Return the role dict or the default role if name is unknown/None."""
    key = _canonical(name)
    if key is None or key not in ROLES:
        return ROLES[DEFAULT_ROLE]
    return ROLES[key]


def is_valid(name):
    key = _canonical(name)
    return key is not None and key in ROLES


def role_names():
    """Ordered list of role keys."""
    return list(ROLES.keys())


def active_tool_names(role_name):
    """Resolve the active tool names for a role.

    Returns None if the role uses ALL tools (caller keeps full schema).
    """
    role = get_role(role_name)
    if role.get("tools") is None and role.get("tool_prefixes") is None:
        return None

    try:
        all_names = list(tools_registry.tool_names())
    except Exception:
        return None

    selected = set()
    prefixes = role.get("tool_prefixes") or []
    for name in all_names:
        for pfx in prefixes:
            if name.startswith(pfx):
                selected.add(name)
                break
    for name in role.get("extra_tools") or []:
        if name in all_names:
            selected.add(name)
    for name in role.get("tools") or []:
        if name in all_names:
            selected.add(name)

    return [n for n in all_names if n in selected]


_STYLE = {
    "general": {"accent": "#8899aa", "chip": "General"},
    "fpa":     {"accent": "#4a90e2", "chip": "FP&A"},
    "quant":   {"accent": "#a855f7", "chip": "Quant"},
    "actuary": {"accent": "#10b981", "chip": "Actuary"},
    "tax":     {"accent": "#f59e0b", "chip": "Tax"},
}


def style(role_name):
    """Return visual style metadata for a role (accent color, chip label)."""
    key = _canonical(role_name) or DEFAULT_ROLE
    return _STYLE.get(key, _STYLE[DEFAULT_ROLE])


def prompt_addon(role_name):
    """Return the role's prompt addon (may be empty string)."""
    return get_role(role_name).get("prompt_addon", "")
