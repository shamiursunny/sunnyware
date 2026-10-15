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
            "  - insurance_data for US state DOI datasets (complaints,\n"
            "    licenses, rate filings) via Socrata public APIs\n"
            "Prefer edgar_* for insurance company financials and fred_* for "
            "macro inputs (rates, inflation). Always state assumptions: "
            "LDF selection, tail factor, discount rate. Verify your numbers."
        ),
        "tool_prefixes": ["edgar_", "fred_", "insurance_"],
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
    "cfo": {
        "label": "Chief Financial Officer",
        "icon": "\U0001F4BC",
        "prompt_addon": (
            "You are the CFO agent \u2014 the user's virtual Chief Financial "
            "Officer and single point of contact for the client.\n"
            "\n"
            "STRICT PIPELINE RULE \u2014 this OVERRIDES any guidance in the "
            "base prompt about 'answering simple questions directly' or "
            "'replying without tools for greetings'. As the CFO agent, "
            "EVERY user request \u2014 including trivial arithmetic, simple "
            "lookups, and short questions \u2014 goes through the pipeline: "
            "you call delegate_to_agent(agent='cdo', ...). No exceptions. "
            "If you think you already know the answer, delegate anyway \u2014 "
            "the CDO will confirm and you will forward the CDO's answer.\n"
            "\n"
            "MANDATORY WORKFLOW (follow in order, no exceptions):\n"
            "  1. Read the client brief.\n"
            "  2. IMMEDIATELY call delegate_to_agent(agent='cdo', "
            "task='<full brief>', context='<format/deadline/files>'). "
            "Call this tool EXACTLY ONCE per user task. Do NOT split the "
            "brief into multiple delegate calls. Do NOT call delegate "
            "again unless the CDO result is clearly broken.\n"
            "  3. Wait for CDO to return the completed deliverable.\n"
            "  4. VERIFY the deliverable matches the brief. If it's "
            "missing something, delegate once more to CDO with a "
            "clarification.\n"
            "  5. FORMAT the final answer as a professional document "
            "(markdown by default).\n"
            "  6. If the user asked to email it, call email_send.\n"
            "\n"
            "FORBIDDEN ACTIONS (do NOT do these yourself):\n"
            "  - Do NOT call rag_search, rag_list, or read_file to look "
            "for information.\n"
            "  - Do NOT write files or run computations.\n"
            "  - Do NOT search the web or query financial APIs.\n"
            "  - Do NOT delegate to anyone other than 'cdo'.\n"
            "\n"
            "If you catch yourself starting to do any of the forbidden "
            "actions, STOP and call delegate_to_agent(agent='cdo', ...) "
            "instead. Every real task goes through CDO. No exceptions.\n"
            "\n"
            "Your final answer to the user is the deliverable itself. "
            "Never reply with a plan, meta-commentary, or 'let me know'."
        ),
        "tool_prefixes": [],
        "extra_tools": [
            "delegate_to_agent",
            "email_send", "email_configured", "email_list_sent",
            "pdf_report", "report_batch",
            "read_file",           # only to pass attachment contents to CDO
            "current_time",
        ],
        "tools": None,
    },

    "cdo": {
        "label": "Chief Delivery Officer",
        "icon": "\U0001F4CB",
        "prompt_addon": (
            "You are the CDO agent \u2014 the Chief Delivery Officer. You "
            "receive tasks ONLY from the CFO agent. You NEVER talk to the "
            "user.\n"
            "\n"
            "MANDATORY WORKFLOW (follow in order, no exceptions):\n"
            "  1. Read the CFO's brief carefully.\n"
            "  2. DECOMPOSE it into 1-5 independent sub-tasks. Prefer 1-3 "
            "well-scoped sub-tasks.\n"
            "  3. For EACH sub-task, immediately call "
            "delegate_to_agent(agent='<worker>', task='<self-contained "
            "sub-task>', context='<shared facts>'). Pick workers from: "
            "actuary, quant, fpa, tax, general.\n"
            "  4. Wait for every worker to return.\n"
            "  5. COMBINE all results into ONE cohesive deliverable \u2014 a "
            "single structured document with all sections integrated.\n"
            "  6. Return the combined deliverable as your final answer.\n"
            "\n"
            "FORBIDDEN ACTIONS (hard limits, no exceptions):\n"
            "  - Do NOT compute, write files, calculate, run python, or "
            "call any tool other than delegate_to_agent.\n"
            "  - Do NOT list files or search RAG.\n"
            "  - Do NOT produce numbers yourself \u2014 all numbers come from "
            "workers you delegate to.\n"
            "  - Do NOT delegate to 'cfo' or 'cdo'.\n"
            "  - Do NOT return scratch work, per-worker sections, or "
            "meta-commentary.\n"
            "  - Do NOT ask the user for clarification \u2014 work with what "
            "the CFO sent.\n"
            "\n"
            "If a sub-task is too broad, split it. If a worker fails, "
            "retry once with a clearer task. If it still fails, note the "
            "gap in the final deliverable.\n"
            "\n"
            "Your final answer is the combined deliverable. Nothing else."
        ),
        "tool_prefixes": [],
        "extra_tools": [
            "delegate_to_agent",
            "read_file",   # only to read brief context CFO passed
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
    "cfo": "cfo", "chief financial officer": "cfo",
    "cdo": "cdo", "chief delivery officer": "cdo",
    "chief": "cfo",
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
    "cfo":     {"accent": "#8b5cf6", "chip": "CFO"},
    "cdo":     {"accent": "#06b6d4", "chip": "CDO"},
}


def style(role_name):
    """Return visual style metadata for a role (accent color, chip label)."""
    key = _canonical(role_name) or DEFAULT_ROLE
    return _STYLE.get(key, _STYLE[DEFAULT_ROLE])


def prompt_addon(role_name):
    """Return the role's prompt addon (may be empty string)."""
    return get_role(role_name).get("prompt_addon", "")


# ── Part 114: delegation matrix + helpers ─────────────────
# Which role may delegate to which roles. Absent = no delegation.
_DELEGATION_MATRIX = {
    "cfo": frozenset({"cdo"}),
    "cdo": frozenset({"actuary", "quant", "fpa", "tax", "general"}),
}


def can_delegate(from_role, to_role):
    """Return True if from_role is permitted to delegate to to_role."""
    frm = _canonical(from_role) or DEFAULT_ROLE
    to = _canonical(to_role) or ""
    if not to:
        return False
    return to in _DELEGATION_MATRIX.get(frm, frozenset())


def delegation_targets(from_role):
    """Return sorted list of roles the from_role may delegate to."""
    frm = _canonical(from_role) or DEFAULT_ROLE
    return sorted(_DELEGATION_MATRIX.get(frm, frozenset()))


# ── Part 116: role config export/import ─────────────────────

def export_roles():
    """Return a JSON-safe snapshot of the role registry.

    Used by GET /api/roles/export to let teams standardize workflows.
    """
    out = []
    for key, r in ROLES.items():
        st = _STYLE.get(key, {})
        out.append({
            "key": key,
            "label": r["label"],
            "icon": r["icon"],
            "accent": st.get("accent", ""),
            "chip": st.get("chip", ""),
            "tool_prefixes": list(r.get("tool_prefixes") or []),
            "extra_tools": list(r.get("extra_tools") or []),
            "delegate_to": sorted(_DELEGATION_MATRIX.get(key, [])),
        })
    return {
        "version": 1,
        "default_role": DEFAULT_ROLE,
        "roles": out,
    }


def import_roles(payload):
    """Validate an exported snapshot. Returns (ok, errors)."""
    errors = []
    if not isinstance(payload, dict):
        return False, ["payload must be an object"]
    if payload.get("version") != 1:
        errors.append("unsupported version: " + str(payload.get("version")))
    roles_in = payload.get("roles")
    if not isinstance(roles_in, list):
        errors.append("'roles' must be a list")
        return False, errors
    known = set(ROLES.keys())
    for i, r in enumerate(roles_in):
        if not isinstance(r, dict):
            errors.append(f"roles[{i}] must be an object")
            continue
        k = r.get("key")
        if not k:
            errors.append(f"roles[{i}]: missing 'key'")
        elif k not in known:
            errors.append(f"roles[{i}]: unknown role '{k}'")
        for f in ("label", "icon"):
            if not r.get(f):
                errors.append(f"roles[{i}]: missing '{f}'")
    return (len(errors) == 0), errors

