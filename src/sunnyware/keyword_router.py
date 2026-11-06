# src/sunnyware/keyword_router.py
"""
Deterministic keyword router. Runs BEFORE Needle 3.
Handles obvious tool matches with 100% accuracy and zero LLM cost.
Returns a dict {"tool": name, "args": {...}} or None.

Only matches when the prompt contains an UNMISTAKABLE keyword.
If there is any ambiguity, returns None and lets Needle 3 handle it.
"""
import re
from typing import Optional


def _extract_number(prompt: str) -> Optional[str]:
    """Try to extract a math expression or number from the prompt."""
    # Look for explicit math expressions like "25 * 4" or "2**10"
    # Match full math expressions like "1/2 + 2", "25 * 4", or "2**10"
    math_match = re.search(r'(\d+(?:\s*[\+\-\*/\*\*]\s*\d+)+)', prompt)
    if math_match:
        return math_match.group(1).strip()
    # Look for "square root of X"
    sqrt_match = re.search(r'square root of (\d+)', prompt, re.IGNORECASE)
    if sqrt_match:
        return f"sqrt({sqrt_match.group(1)})"
    # Look for "X to the power of Y"
    pow_match = re.search(r'(\d+)\s+to the power of\s+(\d+)', prompt, re.IGNORECASE)
    if pow_match:
        return f"{pow_match.group(1)}**{pow_match.group(2)}"
    # Look for "X divided by Y" or "divide X by Y"
    div_match = re.search(r'(?:divide\s+(\d+)\s+by\s+(\d+)|(\d+)\s+divided by\s+(\d+))', prompt, re.IGNORECASE)
    if div_match:
        a = div_match.group(1) or div_match.group(3)
        b = div_match.group(2) or div_match.group(4)
        return f"{a} / {b}"
    # Look for "X times Y" or "multiply X by Y"
    mul_match = re.search(r'(?:multiply\s+(\d+)\s+by\s+(\d+)|(\d+)\s+times\s+(\d+))', prompt, re.IGNORECASE)
    if mul_match:
        a = mul_match.group(1) or mul_match.group(3)
        b = mul_match.group(2) or mul_match.group(4)
        return f"{a} * {b}"
    return None


def _extract_url(prompt: str) -> Optional[str]:
    """Extract a URL from the prompt."""
    match = re.search(r'https?://[^\s\)]+', prompt)
    return match.group(0) if match else None


def _extract_filename(prompt: str, extensions: list) -> Optional[str]:
    """Extract a filename ending in one of the given extensions."""
    for ext in extensions:
        match = re.search(r'([\w\-.]+\.' + ext + r')', prompt, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_timezone(prompt: str) -> str:
    """Extract a location/timezone name."""
    locations = [
        "Tokyo", "London", "New York", "Paris", "Berlin", "Moscow", "Beijing",
        "Sydney", "Dubai", "Singapore", "Toronto", "Chicago", "Los Angeles",
        "Bangladesh", "Dhaka", "Kolkata", "Mumbai", "Delhi", "Bangkok", "Seoul",
        "Hong Kong", "Shanghai", "Rome", "Madrid", "Amsterdam", "Stockholm",
        "Istanbul", "Cairo", "Johannesburg", "Sao Paulo", "Mexico City",
    ]
    for loc in locations:
        if loc.lower() in prompt.lower():
            return loc
    return "UTC"


def keyword_route(prompt: str) -> Optional[dict]:
    print(f"[keyword_router] DEBUG: Checking prompt: '{prompt[:50]}'", flush=True)
    import re as _re_bi
    _p_low_bi = prompt.lower()
    p = prompt.lower()

    # --- Quant & ML Routes (v1.5.0) ---
    _ta_match = re.search(r'technical analysis.*?([\w\-]+\.csv)', prompt, re.IGNORECASE)
    if _ta_match:
        return {"tool": "technical_analysis", "args": {"filename": _ta_match.group(1)}}

    _ml_match = re.search(r'(?:forecast|predict)\s+([\w]+).*?([\w\-]+\.csv)', prompt, re.IGNORECASE)
    if _ml_match:
        return {"tool": "ml_forecast", "args": {"target_column": _ml_match.group(1), "filename": _ml_match.group(2), "periods": 5}}

    _pro_chart = re.search(r'(?:candlestick|correlation|heatmap).*?([\w\-]+\.csv)', prompt, re.IGNORECASE)
    if _pro_chart:
        chart_type = "candlestick" if "candlestick" in prompt.lower() else "correlation"
        return {"tool": "pro_chart", "args": {"chart_type": chart_type, "filename": _pro_chart.group(1)}}

    # --- Multi-Provider Aggregator ---
    _agg_match = re.search(r'(?:aggregate|multi-provider)\s+(?:stock\s+)?(?:data\s+)?(?:for\s+)?([a-zA-Z]{1,5})\b', prompt, re.IGNORECASE)
    if _agg_match:
        return {"tool": "aggregate_market_data", "args": {"symbol": _agg_match.group(1).upper()}}

    # --- Persistent Python Session ---
    if "run in session:" in p or "python session:" in p:
        code = prompt.split(":", 1)[1].strip()
        return {"tool": "python_session", "args": {"code": code, "session_id": "default"}}

    # --- Vision Analyze ---
    _vision_match = re.search(r'(?:analyze|look at|describe)\s+(?:the\s+)?(?:image|chart|file)\s+([\w\-]+\.(?:png|jpg|jpeg))', prompt, re.IGNORECASE)
    if _vision_match:
        return {"tool": "vision_analyze", "args": {"filename": _vision_match.group(1), "prompt": prompt}}

    # --- Live Market Stream ---
    if ("stream" in prompt.lower() or "live" in prompt.lower()) and ("price" in prompt.lower() or "market" in prompt.lower()):
        _sym = re.search(r'(?:for|of)\s+([a-zA-Z]{1,5})\b', prompt, re.IGNORECASE)
        if not _sym:
            _sym = re.search(r'\b([A-Z]{2,5})\b', prompt)
        if _sym:
            return {"tool": "live_market_stream", "args": {"symbol": _sym.group(1).upper(), "duration_seconds": 10}}

    # --- Insurance Research (lenient) ---
    _ins_match = re.search(r'insurance\s+(?:research|data)\s+(?:for\s+|on\s+)?(.+)', prompt, re.IGNORECASE)
    if _ins_match:
        return {"tool": "insurance_research", "args": {"action": "search_filings", "query": _ins_match.group(1).strip()}}

    # --- Legal Citation (lenient) ---
    _legal_match = re.search(r'(?:legal\s+)?citation\s+(?:check|verify|lookup|validate)\s+(.+)', prompt, re.IGNORECASE)
    if _legal_match:
        return {"tool": "legal_citation_check", "args": {"action": "verify_text", "text": _legal_match.group(1).strip()}}

    # --- Calculator ---
    num = _extract_number(prompt)
    if num:
        return {"tool": "calculator", "args": {"expression": num}}

    # --- Web Search ---
    if any(kw in p for kw in ["search the web", "google", "search web"]):
        q = prompt.lower().split("for")[-1].strip() if "for" in prompt.lower() else prompt
        return {"tool": "web_search", "args": {"query": q}}

    # --- Web Fetch ---
    if "fetch" in p or "get page" in p:
        url = _extract_url(prompt)
        if url: return {"tool": "web_fetch", "args": {"url": url}}

    # --- Email ---
    if "email" in p:
        return {"tool": "email_configured", "args": {}}

    # --- PDF / Excel ---
    if ".pdf" in p:
        m = re.search(r'([\w\-]+\.pdf)', prompt, re.IGNORECASE)
        if m: return {"tool": "pdf_read", "args": {"file": m.group(1)}}
    if ".xlsx" in p:
        m = re.search(r'([\w\-]+\.xlsx)', prompt, re.IGNORECASE)
        if m: return {"tool": "excel_read", "args": {"file": m.group(1)}}

    # --- SQL Sandbox ---
    if "sql sandbox create" in p or "create sql sandbox" in p:
        return {"tool": "sql_sandbox_create", "args": {"name": "sandbox"}}
    if "sql sandbox load csv" in p or "load csv" in p:
        m = re.search(r'([\w\-]+\.csv)', prompt, re.IGNORECASE)
        return {"tool": "sql_sandbox_load_csv", "args": {"file": m.group(1) if m else ""}}
    if "sql sandbox execute" in p or "execute sql" in p:
        q = prompt.split(":")[-1].strip() if ":" in prompt else prompt
        return {"tool": "sql_sandbox_execute", "args": {"sql": q}}
    if "sql sandbox list" in p or "list sql sandbox" in p:
        return {"tool": "sql_sandbox_list", "args": {}}

    # --- Browser ---
    if "browser goto" in p:
        m = re.search(r'https?://[^\s]+', prompt)
        return {"tool": "browser_goto", "args": {"url": m.group(0) if m else ""}}

    # --- Chart from data ---
    if "chart" in p and "[" in p:
        return {"tool": "chart_from_data", "args": {"data": prompt.split("chart")[-1].strip(), "chart_type": "bar"}}

    # --- Research ---
    if "research search" in p:
        return {"tool": "research_search", "args": {"query": prompt.split("research search")[-1].strip()}}

    """
    Match obvious tool intent using keywords and regex extraction.
    Returns {"tool": name, "args": {...}} or None.
    """
    # --- sandbox file tools (write / read) ---
    # This MUST be checked early — before generic "write file" / "read file" blocks.
    if "sandbox" in (prompt or "").lower():
        _pl = (prompt or "").lower()

        # WRITE: "write/save/create a file called X to sandbox [with content '...']"
        _m_write = re.search(
            r"(?:write|save|create|store|put)\s+(?:a\s+|the\s+)?(?:file\s+)?"
            r"(?:called|named|as)?\s*['\"\u2018\u2019]?([\w.\-]+\.[A-Za-z0-9]+)['\"\u2018\u2019]?"
            r".*?(?:to|in|into|inside)\s+(?:the\s+)?sandbox",
            _pl,
        )
        if _m_write:
            _fname = _m_write.group(1).strip()
            _content = ""
            _cm = re.search(
                r"(?:with\s+content|containing|content\s*[:=])\s*['\"\u2018\u2019\u201c\u201d`](.+?)['\"\u2018\u2019\u201c\u201d`]",
                prompt,
                re.IGNORECASE | re.DOTALL,
            )
            if _cm:
                _content = _cm.group(1)
            return {"tool": "write_sandbox_file", "args": {"file": _fname, "content": _content}}

        # READ: "read/open/show X from sandbox" or "read sandbox file X"
        _m_read = re.search(
            r"(?:read|open|show|get|view|display|cat|see)\s+(?:me\s+)?(?:the\s+)?"
            r"(?:sandbox\s+)?(?:file\s+)?['\"\u2018\u2019]?([\w.\-]+\.[A-Za-z0-9]+)['\"\u2018\u2019]?",
            _pl,
        )
        if _m_read:
            _ext_read = _m_read.group(1).split('.')[-1].lower()
            # Skip BI/Office extensions — those go to read_bi_file
            if _ext_read not in ("pbix", "twb", "twbx", "xls", "xlsm", "xlsx", "docx", "doc", "pptx", "ppt"):
                return {"tool": "read_sandbox_file", "args": {"file": _m_read.group(1).strip()}}

    p = prompt.lower()



    # --- export_table (save data as CSV/JSON) ---
    # Export patterns: "export/save X to/as CSV" OR "save as X.csv"
    _export_match = _re_bi.search(
        r"(export|save|download|write)\s+(?:the\s+)?(?:data|table|sheet|result|it|this)?\s*(?:to|as)\s+(?:a\s+)?(?:csv|json|tsv)\b",
        _p_low_bi
    )
    _save_as_match = _re_bi.search(r"(?:save|export|write|download)\s+as\s+[\x27\x22]?([\w.\-]+\.(?:csv|json|tsv))[\x27\x22]?", _p_low_bi)
    _save_the_as_match = _re_bi.search(r"(?:save|export|write|download)(?:\s+\w+){1,5}?\s+as\s+[\x27\x22]?([\w.\-]+\.(?:csv|json|tsv))[\x27\x22]?", _p_low_bi)
    if _export_match or _save_as_match or _save_the_as_match:
        _target_kind = "sandbox"
        if "workspace" in _p_low_bi:
            _target_kind = "workspace"
        _fname_match = _re_bi.search(r"['\"]?([\w.\-]+\.(?:csv|json|tsv))['\"]?", prompt, _re_bi.IGNORECASE)
        _out_name = _fname_match.group(1) if _fname_match else "export.csv"
        return {"tool": "export_table", "args": {"filename": _out_name, "target_kind": _target_kind}}

    # --- write_file (simple "write a file called X.txt with content Y") ---
    _wf_match = _re_bi.search(
        r"(?:write|save|create)\s+(?:a\s+)?file\s+(?:called|named)?\s*[\x27\x22]?([\w.\-]+\.txt)[\x27\x22]?",
        _p_low_bi
    )
    if _wf_match:
        _wf_fname = _wf_match.group(1)
        # Try quoted content first, then unquoted (rest of line)
        _content_m = _re_bi.search(
            r"(?:with\s+content|containing|content\s*[:=])\s*[\x27\x22](.+?)[\x27\x22]",
            prompt, _re_bi.IGNORECASE
        )
        if not _content_m:
            _content_m = _re_bi.search(
                r"(?:with\s+content|containing|content\s*[:=])\s+(.+?)$",
                prompt, _re_bi.IGNORECASE | _re_bi.MULTILINE
            )
        _content = _content_m.group(1).strip() if _content_m else ""
        return {"tool": "write_file", "args": {"path": _wf_fname, "content": _content}}

    # --- csv_query (simple "read csv file X") ---
    _csv_simple = _re_bi.search(
        r"(?:read|open|show|query|select\s+from)\s+(?:the\s+)?(?:csv\s+)?file\s+[\x27\x22]?([\w.\-]+\.csv)[\x27\x22]?",
        _p_low_bi
    )
    if _csv_simple:
        _csv_fname = _csv_simple.group(1)
        return {"tool": "csv_query", "args": {"file": _csv_fname, "sql": f"SELECT * FROM {_csv_fname}"}}



    # --- date_calc ---
    # "add N days to YYYY-MM-DD" / "subtract N days from YYYY-MM-DD"
    import re as _re_dc
    m = _re_dc.search(r'(add|subtract)\s+(\d+)\s+days?\s+(?:to|from)\s+(\d{4}-\d{2}-\d{2})', prompt, _re_dc.IGNORECASE)
    if m:
        op, n, d = m.group(1).lower(), int(m.group(2)), m.group(3)
        if op == 'subtract':
            n = -n
        return {"tool": "date_calc", "args": {"action": "add", "date": d, "days": n}}
    # "days between YYYY-MM-DD and YYYY-MM-DD"
    m = _re_dc.search(r'(?:days|difference)\s+between\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})', prompt, _re_dc.IGNORECASE)
    if m:
        return {"tool": "date_calc", "args": {"action": "diff", "date": m.group(1), "date2": m.group(2)}}
    # "what day of the week is YYYY-MM-DD"
    m = _re_dc.search(r'(?:day of (?:the )?week|weekday)\s+(?:is|for)\s+(\d{4}-\d{2}-\d{2})', prompt, _re_dc.IGNORECASE)
    if not m:
        m = _re_dc.search(r'(\d{4}-\d{2}-\d{2})\s+(?:is what day|weekday)', prompt, _re_dc.IGNORECASE)
    if m:
        return {"tool": "date_calc", "args": {"action": "weekday", "date": m.group(1)}}

    # --- risk_metrics ---
    if any(kw in p for kw in ["risk metrics", "sharpe ratio", "sortino ratio", "calmar ratio",
                               "var ", "cvar ", "drawdown", "volatility", "stress test",
                               "correlation", "beta"]):
        import re as _re_rm
        arr_match = _re_rm.search(r'\[([-\d.,\s]+)\]', prompt)
        if arr_match:
            action = "summary"
            if "sharpe" in p:
                action = "sharpe"
            elif "sortino" in p:
                action = "sortino"
            elif "calmar" in p:
                action = "calmar"
            elif "cvar" in p:
                action = "cvar"
            elif "var" in p:
                action = "var"
            elif "drawdown" in p:
                action = "drawdown"
            elif "volatility" in p:
                action = "volatility"
            elif "stress" in p:
                action = "stress_test"
            elif "correlation" in p:
                action = "correlation"
            elif "beta" in p:
                action = "beta"
            elif "from prices" in p:
                action = "from_prices"
            return {"tool": "risk_metrics", "args": {"action": action, "returns": arr_match.group(0)}}
        return None

    # --- forecast_arima ---
    if any(kw in p for kw in ["forecast arima", "arima forecast", "forecast for",
                               "forecast periods", "forecast 10 periods"]):
        import re as _re_fa
        arr_match = _re_fa.search(r'\[([-\d.,\s]+)\]', prompt)
        if arr_match:
            periods = 6
            pm = _re_fa.search(r'forecast\s+(\d+)\s+periods?', prompt, _re_fa.IGNORECASE)
            if pm:
                periods = int(pm.group(1))
            import json as _json
            try:
                data_list = _json.loads(arr_match.group(0))
                return {"tool": "forecast_arima", "args": {"data": data_list, "periods": periods}}
            except Exception:
                return None
        return None

    # --- auditor_full_spec ---
    if any(kw in p for kw in ["auditor spec", "full auditor spec", "auditor specification", "auditor full spec"]):
        return {"tool": "auditor_full_spec", "args": {}}

    # --- Math regex (catches '2+2' etc.) ---
    import re as _re
    _math_match = _re.search(r'(?:what is|calculate|compute|evaluate)?\s*(-?\d+(?:\.\d+)?\s*[\+\-\*\/\%\^]\s*-?\d+(?:\.\d+)?(?:\s*[\+\-\*\/\%\^]\s*-?\d+(?:\.\d+)?)*)', prompt.lower())
    if _math_match:
        expr = _math_match.group(1).strip()
        if all(c in '0123456789+-*/%^() .' for c in expr):
            return {"tool": "calculator", "args": {"expression": expr}}

    # --- Tip / percent calculation ---
    import re as _re_tip
    m_tip = _re_tip.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:tip\s+)?(?:on|of)\s*(\d+(?:\.\d+)?)', prompt.lower())
    if m_tip:
        pct = float(m_tip.group(1))
        base = float(m_tip.group(2))
        expr = f"{base} * {pct} / 100"
        return {"tool": "calculator", "args": {"expression": expr}}

    # Generic percent word ("18 percent tip on 85")
    m_pct = _re_tip.search(r'(\d+(?:\.\d+)?)\s*(?:percent|%)\s+(?:tip|of)\s+(\d+(?:\.\d+)?)', prompt.lower())
    if m_pct:
        pct = float(m_pct.group(1))
        base = float(m_pct.group(2))
        expr = f"{base} * {pct} / 100"
        return {"tool": "calculator", "args": {"expression": expr}}

# --- calculator ---
    calc_keywords = ["calculate", "compute", "math", "square root", "sqrt",
                     "multiply", "divide", "what is", "how much is",
                     "tip", "percent", "percentage", "split", "average"]
    if any(kw in p for kw in calc_keywords):
        expr = _extract_number(prompt)
        if expr:
            return {"tool": "calculator", "args": {"expression": expr}}

    # --- current_time (only when it has "time" AND location OR "what time") ---
    time_keywords = ["what time", "current time", "the time in", "time is it",
                     "clock", "tell me the time"]
    if any(kw in p for kw in time_keywords):
        tz = _extract_timezone(prompt)
        return {"tool": "current_time", "args": {"timezone": tz}}

    # --- browser_screenshot (URL + screenshot trigger) ---
    if any(kw in p for kw in ["screenshot of ", "take a screenshot", "take screenshot",
                                "capture http", "capture the site", "capture the page",
                                "snapshot of ", "capture this url", "capture url "]):
        import re as _re_bs
        url_m = _re_bs.search(r"(https?://[^\s]+)", prompt)
        if url_m:
            return {"tool": "browser_screenshot", "args": {"url": url_m.group(1)}}

    # --- browser_goto (URL + open/visit/browse) ---
    if any(kw in p for kw in ["open http", "open https", "visit http", "visit https",
                                "browse to ", "navigate to ", "go to http", "go to https"]):
        import re as _re_bg
        url_m = _re_bg.search(r"(https?://[^\s]+)", prompt)
        if url_m:
            return {"tool": "browser_goto", "args": {"url": url_m.group(1)}}

    # --- recall_history ---
    if any(kw in p for kw in ["recall our last", "recall history", "remember last",
                               "what did we discuss", "find where i mentioned"]):
        import re as _re_rh
        m = _re_rh.search(
            r'(?:recall(?: our)?(?: last)?(?:\s+\w+)?\s+about|what did we discuss about|find where i mentioned)\s+(.+)',
            prompt, _re_rh.IGNORECASE
        )
        if m:
            query = m.group(1).strip()
            args = {"query": query}
            # Extract optional days: "last 30 days" / "past 7 days"
            dm = _re_rh.search(r'(?:last|past)\s+(\d+)\s+days?', prompt, _re_rh.IGNORECASE)
            if dm:
                args["days"] = int(dm.group(1))
                query = _re_rh.sub(r'(?:last|past)\s+\d+\s+days?', '', query, flags=_re_rh.IGNORECASE).strip()
            # Extract optional limit: "limit 5" / "top 5"
            lm = _re_rh.search(r'(?:limit|top)\s+(\d+)', prompt, _re_rh.IGNORECASE)
            if lm:
                args["limit"] = int(lm.group(1))
                query = _re_rh.sub(r'(?:limit|top)\s+\d+', '', query, flags=_re_rh.IGNORECASE).strip()
            args["query"] = query
            return {"tool": "recall_history", "args": args}
        return None

    # --- memory_search ---
    if any(kw in p for kw in ["search memory for", "memory search for"]):
        import re as _re_ms
        m = _re_ms.search(
            r'(?:search memory for|memory search for)\s+(.+)',
            prompt, _re_ms.IGNORECASE
        )
        if m:
            query = m.group(1).strip()
            args = {"query": query}
            # Extract optional days: "last 30 days" / "past 7 days"
            dm = _re_ms.search(r'(?:last|past)\s+(\d+)\s+days?', prompt, _re_ms.IGNORECASE)
            if dm:
                args["days"] = int(dm.group(1))
                query = _re_ms.sub(r'(?:last|past)\s+\d+\s+days?', '', query, flags=_re_ms.IGNORECASE).strip()
            # Extract optional limit: "limit 5" / "top 5"
            lm = _re_ms.search(r'(?:limit|top)\s+(\d+)', prompt, _re_ms.IGNORECASE)
            if lm:
                args["limit"] = int(lm.group(1))
                query = _re_ms.sub(r'(?:limit|top)\s+\d+', '', query, flags=_re_ms.IGNORECASE).strip()
            args["query"] = query
            return {"tool": "memory_search", "args": args}
        return None

    # --- weather (1-3 word cities + accents) ---
    if "weather" in p:
        import re as _re_w
        city_match = _re_w.search(
            r"(?:in|at|for|of)\s+([A-Z\u00C0-\u024F][a-zA-Z\u00C0-\u024F]+(?:\s+[A-Z\u00C0-\u024F][a-zA-Z\u00C0-\u024F]+){0,2})",
            prompt
        )
        if city_match:
            return {"tool": "weather", "args": {"city": city_match.group(1)}}
        # No city detected; let LLM ask the user


    # --- email_send ---
    if any(kw in p for kw in ["send an email", "send email", "email to", "mail to"]):
        import re as _re_e
        to_match = _re_e.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", prompt)
        if to_match:
            subj_match = _re_e.search(r"(?:about|regarding|subject:?)\s+([^,\.\n]+)", prompt)
            subject = subj_match.group(1).strip() if subj_match else "Message from Sunnyware"
            import os as _os_e
            if not _os_e.getenv("RESEND_API_KEY"):
                return {"tool": "email_configured", "args": {}}
            # Strip command prefix and email from the body
            body = prompt
            body = _re_e.sub(r'(?:send\s+(?:an\s+)?email\s+to\s+|email\s+to\s+|mail\s+to\s+)', '', body, flags=_re_e.IGNORECASE)
            body = _re_e.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', body)
            body = body.strip().strip('.,;:') or prompt
            return {"tool": "email_send", "args": {
                "to": to_match.group(1),
                "subject": subject,
                "body": body,
            }}


    # --- citation_lookup ---
    if any(kw in p for kw in ["look up citation", "find citation", "citation for"]):
        import re as _re_cl
        m = _re_cl.search(
            r'(?:look up citation|find citation|citation for)\s+(.+)',
            prompt, _re_cl.IGNORECASE
        )
        if m:
            return {"tool": "citation_lookup", "args": {"query": m.group(1).strip()}}
        return None

    # --- fred_economic ---
    if any(kw in p for kw in ["search economic data for", "search fred for"]):
        import re as _re_fs
        m = _re_fs.search(r'(?:search economic data for|search fred for)\s+(.+)', prompt, _re_fs.IGNORECASE)
        if m:
            return {"tool": "fred_economic", "args": {"action": "search", "query": m.group(1).strip()}}
        return None

    if any(kw in p for kw in ["economic data for", "fred series for", "economic indicator for"]):
        import re as _re_fe
        m = _re_fe.search(r'(?:economic data for|fred series for|economic indicator for)\s+([A-Z0-9]+)', prompt)
        if m:
            return {"tool": "fred_economic", "args": {"action": "series", "series_id": m.group(1)}}
        return None

    if any(kw in p for kw in ["popular economic indicators", "list popular economic indicators"]):
        return {"tool": "fred_economic", "args": {"action": "popular"}}

    # --- tiingo_prices ---
    if any(kw in p for kw in ["historical prices for", "intraday prices for", "ticker info for"]):
        import re as _re_ti
        action = "eod"
        if "intraday" in p: action = "intraday"
        elif "ticker info" in p: action = "meta"
        m = _re_ti.search(r'(?:historical prices for|intraday prices for|ticker info for)\s+([A-Z]{1,5})', prompt)
        if m:
            return {"tool": "tiingo_prices", "args": {"action": action, "ticker": m.group(1)}}
        return None

    # --- twelvedata_prices ---
    if any(kw in p for kw in ["market quote for", "time series for", "rsi for", "macd for"]):
        import re as _re_td
        action = "quote"
        if "time series" in p: action = "time_series"
        elif "rsi" in p: action = "rsi"
        elif "macd" in p: action = "macd"
        m = _re_td.search(r'(?:market quote for|time series for|rsi for|macd for)\s+([A-Z0-9/]+)', prompt)
        if m:
            return {"tool": "twelvedata_prices", "args": {"action": action, "symbol": m.group(1)}}
        return None

    # --- marketaux_news ---
    if any(kw in p for kw in ["news for", "financial news for", "news about"]):
        import re as _re_mn
        m = _re_mn.search(r'(?:news for|financial news for|news about)\s+([A-Z,]+)', prompt)
        if m:
            return {"tool": "marketaux_news", "args": {"symbols": m.group(1)}}
        return None

    # --- edgar_fundamentals ---
    if any(kw in p for kw in ["sec financials for", "edgar financials for", "sec filings for"]):
        import re as _re_ef
        statement = "all"
        if "income statement" in p: statement = "income"
        elif "balance sheet" in p: statement = "balance"
        elif "cash flow" in p: statement = "cashflow"
        m = _re_ef.search(r'(?:sec financials for|edgar financials for|sec filings for)\s+([A-Z]{1,5})', prompt)
        if m:
            return {"tool": "edgar_fundamentals", "args": {"ticker": m.group(1), "statement": statement}}
        return None

    # --- govcon_data (simple actions) ---
    if any(kw in p for kw in ["search government contracts for", "government contracts for"]):
        import re as _re_gc
        m = _re_gc.search(r'(?:search government contracts for|government contracts for)\s+(.+)', prompt, _re_gc.IGNORECASE)
        if m:
            return {"tool": "govcon_data", "args": {"action": "award_search", "keyword": m.group(1).strip()}}
        return None

    if any(kw in p for kw in ["search government recipients for", "government recipients for"]):
        import re as _re_gr
        m = _re_gr.search(r'(?:search government recipients for|government recipients for)\s+(.+)', prompt, _re_gr.IGNORECASE)
        if m:
            return {"tool": "govcon_data", "args": {"action": "recipient_search", "keyword": m.group(1).strip()}}
        return None

    # --- eulerpool_data (simple profile lookup) ---
    if any(kw in p for kw in ["eulerpool profile for", "eulerpool data for"]):
        import re as _re_ep
        m = _re_ep.search(r'(?:eulerpool profile for|eulerpool data for)\s+([A-Z]{1,5})', prompt)
        if m:
            return {"tool": "eulerpool_data", "args": {"action": "profile", "identifier": m.group(1)}}
        return None

    # --- mkdir ---
    if any(kw in p for kw in ["create directory", "make directory", "mkdir"]):
        import re as _re_mk
        m = _re_mk.search(r'(?:create directory|make directory|mkdir)\s+([\w\-./\\]+)', prompt, _re_mk.IGNORECASE)
        if m:
            return {"tool": "mkdir", "args": {"path": m.group(1)}}
        return None

    # --- financial_metrics ---
    if any(kw in p for kw in ["financial metrics for", "calculate financial metrics for"]):
        import re as _re_fm
        arr_match = _re_fm.search(r'\[([-\d.,\s]+)\]', prompt)
        if arr_match:
            return {"tool": "financial_metrics", "args": {"returns": arr_match.group(0)}}
        return None

    # --- web_search ---
    if any(kw in p for kw in ["search the web", "search web", "google ", "look up online", "search online"]):
        import re as _re_ws
        q_match = _re_ws.search(r"(?:search (?:the )?web(?: for)?|google|look up online|search online)\s+(.+)", prompt, _re_ws.IGNORECASE)
        if q_match:
            return {"tool": "web_search", "args": {"query": q_match.group(1).strip()}}

    # --- image_generate (handles "generate an image", "create image", etc.) ---
    if any(kw in p for kw in ["generate image", "generate an image", "create image", "create an image",
                               "draw ", "make an image", "make image", "image of"]):
        import re as _re_ig
        q_match = _re_ig.search(
            r"(?:generate|create|make|draw)\s+(?:an?\s+)?image(?:\s+of|\s+showing)?\s+(.+)",
            prompt, _re_ig.IGNORECASE
        )
        if q_match:
            return {"tool": "image_generate", "args": {"prompt": q_match.group(1).strip()}}


    # --- pdf_read (must have .pdf extension, and not be a compare/diff prompt) ---
    if ".pdf" in p and not any(kw in p for kw in ["create", "generate", "make", "build", "write a pdf", "compare", "diff"]):
        fname = _extract_filename(prompt, ["pdf"])
        if fname:
            return {"tool": "pdf_read", "args": {"file": fname}}

    # --- narrate_table (needs JSON rows — keyword can't extract) ---
    if "narrate" in p and "table" in p:
        return None
    if "explain this table" in p or "describe this table" in p:
        return None

    # --- financial_metrics (LLM-only — requires structured financial data) ---
    if "financial metrics" in p or "stock metrics" in p or "investment metrics" in p:
        return None

    # --- data_quality_report (must come before generic file handlers) ---
    if any(kw in p for kw in ["data quality report", "quality check",
                               "check data quality", "data quality of",
                               "data quality for"]):
        import re as _re_dq
        f_match = _re_dq.search(
            r'([\w\-./\\]+\.(?:csv|tsv|xlsx|xls|parquet|json))',
            prompt, _re_dq.IGNORECASE
        )
        if not f_match:
            return None
        args = {"file": f_match.group(1)}
        mr = _re_dq.search(
            r'(?:max_rows\s*=\s*|max\s+|limit\s+|first\s+|with\s+)(\d{1,9})(?:\s*rows?)?',
            prompt, _re_dq.IGNORECASE
        )
        if mr:
            try:
                args["max_rows"] = int(mr.group(1))
            except ValueError:
                pass
        sp = _re_dq.search(
            r'sample_pct\s*=\s*(\d+(?:\.\d+)?)'
            r'|sample\s+(\d+(?:\.\d+)?)\s*(?:%|percent)'
            r'|(\d+(?:\.\d+)?)\s*%\s*sample',
            prompt, _re_dq.IGNORECASE
        )
        if sp:
            val = sp.group(1) or sp.group(2) or sp.group(3)
            try:
                args["sample_pct"] = float(val)
            except (ValueError, TypeError):
                pass
        return {"tool": "data_quality_report", "args": args}

    # --- sql_sandbox_drop ---
    if any(kw in p for kw in ["drop sql sandbox", "delete sql sandbox",
                               "drop sandbox", "delete sandbox"]):
        import re as _re_drop
        m = _re_drop.search(
            r'(?:drop|delete)\s+(?:sql\s+)?sandbox\s+(?:named\s+)?([a-z_][a-z0-9_]*)',
            prompt, _re_drop.IGNORECASE
        )
        if m:
            return {"tool": "sql_sandbox_drop", "args": {"name": m.group(1)}}
        return None


    # --- sql_sandbox_load_csv (must come before generic csv handler) ---
    if any(kw in p for kw in ["load", "import"]) and "sandbox" in p and any(x in p for x in [".csv", ".tsv"]):
        import re as _re_ld
        m = _re_ld.search(
            r'load\s+([\w\-./\\]+\.(?:csv|tsv))'
            r'(?:\s+into\s+table\s+([a-z_][a-z0-9_]*))?'
            r'\s+(?:in|into)\s+sandbox\s+([a-z_][a-z0-9_]*)',
            prompt, _re_ld.IGNORECASE
        )
        if m:
            file_ = m.group(1)
            table = (m.group(2) or
                     file_.rsplit('.', 1)[0].rsplit('/', 1)[-1].rsplit('\\', 1)[-1])
            return {"tool": "sql_sandbox_load_csv",
                    "args": {"name": m.group(3), "file": file_, "table": table}}
        return None

    # --- sql_sandbox_execute ---
    if any(kw in p for kw in ["run sql in sandbox", "execute sql in sandbox",
                               "query sandbox", "run query in sandbox",
                               "execute query in sandbox"]):
        import re as _re_ex
        m = _re_ex.search(
            r'(?:run|execute|query)(?:\s+(?:sql|query))?\s+(?:in\s+)?sandbox\s+([a-z_][a-z0-9_]*)\s*:?\s*(.+)$',
            prompt, _re_ex.IGNORECASE | _re_ex.DOTALL
        )
        if not m:
            return None
        args = {"name": m.group(1), "sql": m.group(2).strip()}
        pm = _re_ex.search(
            r'(?:with\s+params?\s*[=:]?\s*|params?\s*=\s*)\[([^\]]+)\]',
            args["sql"], _re_ex.IGNORECASE
        )
        if pm:
            import json as _json
            try:
                args["params"] = _json.loads("[" + pm.group(1) + "]")
                args["sql"] = args["sql"][:pm.start()].strip().rstrip(",;")
            except Exception:
                pass
        return {"tool": "sql_sandbox_execute", "args": args}

    # --- sql_sandbox_list ---
    if any(kw in p for kw in ["list sql sandboxes", "list sandboxes",
                               "show sql sandboxes", "show sandboxes",
                               "my sql sandboxes", "all sql sandboxes"]):
        return {"tool": "sql_sandbox_list", "args": {}}

    # --- generate_chart (v1.4.0) — BEFORE csv_query so .csv doesn't hijack ---
    _chart_m = re.search(
        r"\b(?:generate|create|make|build|draw)\s+(?:a\s+)?(?:bar|line|pie|histogram|donut|scatter)?\s*(?:chart|graph|plot|visualization)\b.*?([\w\-./\\]+\.[a-zA-Z0-9]+)",
        prompt, re.IGNORECASE
    )
    if _chart_m:
        fname = _chart_m.group(1)
        ctype_m = re.search(r"\b(bar|line|pie|histogram|donut|scatter)\b", prompt, re.IGNORECASE)
        chart_type = ctype_m.group(1).lower() if ctype_m else "bar"
        return {
            "tool": "generate_chart",
            "args": {
                "filename": fname,
                "chart_type": "bar" if chart_type == "histogram" else ("pie" if chart_type == "donut" else chart_type),
                "x_column": "x",
                "y_column": "y",
            }
        }
    # --- excel_read (must have .xlsx) ---
    if "excel" in p or ".xlsx" in p:
        fname = _extract_filename(prompt, ["xlsx"])
        if fname:
            action = "write" if any(w in p for w in ["write", "save", "create"]) else "read"
            if action == "read":
                return {"tool": "excel_read", "args": {"file": fname}}
            # write needs structured data (sheets array) — let LLM handle
            return None

    # --- delete_file (accepts "delete X.txt" OR "delete file X.txt") ---
    _df_m = re.search(
        r'\b(?:delete|remove)\s+(?:the\s+)?(?:file\s+)?([\w\-./\\]+\.[a-zA-Z0-9]+)',
        prompt, re.IGNORECASE
    )
    if _df_m:
        return {"tool": "delete_file", "args": {"path": _df_m.group(1)}}


    # --- sql_sandbox_create (v1.4.0) ---
    if re.search(r"\b(?:create|new|start|make)\s+(?:a\s+)?(?:sql|sqlite|database)\s+(?:sandbox|db|database)\b", prompt, re.IGNORECASE) or        re.search(r"\bsql\s+(?:sandbox|db|database)\s+(?:create|new|start)\b", prompt, re.IGNORECASE):
        return {"tool": "sql_sandbox_create", "args": {"name": "sandbox"}}

    # --- csv_query (must have .csv) ---
    if ".csv" in p or "csv file" in p:
        fname = _extract_filename(prompt, ["csv"])
        if fname:
            import re as _re_csv
            # Try to extract explicit SQL first
            sql_match = _re_csv.search(r'(select\s+.+?)(?:\s*$|\s*from\s+[^\s]+)', prompt, _re_csv.IGNORECASE)
            if sql_match and "select" in sql_match.group(1).lower():
                sql = sql_match.group(1).strip()
                if " from " not in sql.lower():
                    sql = f"{sql} FROM {fname}"
                return {"tool": "csv_query", "args": {"file": fname, "sql": sql}}
            # Try "query X for Y" / "select * from X"
            if "all rows" in p or "all data" in p or "everything" in p:
                return {"tool": "csv_query", "args": {"file": fname, "sql": f"SELECT * FROM {fname}"}}
            # Try "select * from X"
            if "select" in p and "*" in p:
                return {"tool": "csv_query", "args": {"file": fname, "sql": f"SELECT * FROM {fname}"}}
            # Try "query for X" pattern
            q_match = _re_csv.search(r'query(?:\s+\w+)?\s+for\s+(.+)$', prompt, _re_csv.IGNORECASE)
            if q_match:
                return {"tool": "csv_query", "args": {"file": fname, "sql": f"SELECT * FROM {fname} WHERE {q_match.group(1).strip()}"}}
            # Fall through to LLM for complex SQL
            return None

    # --- rag_search for document reads (RAG store has priority over local read_file) ---
    if ".txt" in p or ".pdf" in p or ".md" in p or ".csv" in p or ".docx" in p:
        fname = _extract_filename(prompt, ["txt", "pdf", "md", "csv", "docx"])
        if fname and any(w in p for w in ["read", "open", "contents", "show", "summarize", "check", "search"]):
            return {"tool": "rag_search", "args": {"query": fname}}

    # --- read_file for explicit local workspace reads (only if "workspace" or "local" is mentioned) ---
    if ".txt" in p and ("workspace" in p or "local" in p):
        fname = _extract_filename(prompt, ["txt"])
        if fname and any(w in p for w in ["read", "open", "contents", "show"]):
            return {"tool": "read_file", "args": {"path": fname}}

    # --- write_file (must have .txt) ---
    if any(w in p for w in ["write", "save", "create"]) and ".txt" in p:
        fname = _extract_filename(prompt, ["txt"])
        if fname:
            import re as _re_wf
            # Try to extract content from quotes: write 'hello' to file.txt
            content_m = _re_wf.search(r"['\"]([^'\"]+)['\"]", prompt)
            if content_m:
                return {"tool": "write_file", "args": {"path": fname, "content": content_m.group(1)}}
            # Try "write X to file.txt" pattern
            content_m = _re_wf.search(r"(?:write|save)\s+(.+?)\s+to\s+", prompt, _re_wf.IGNORECASE)
            if content_m:
                return {"tool": "write_file", "args": {"path": fname, "content": content_m.group(1).strip()}}
            # No content detected — let LLM handle
            return None

    # --- url_metadata (must have URL + "metadata" or "og tags" etc.) ---
    if any(kw in p for kw in ["metadata of ", "metadata for ", "get metadata", "extract metadata",
                                "og tags", "open graph", "meta tags of", "url info for"]):
        import re as _re_um
        url_m = _re_um.search(r"(https?://[^\s]+)", prompt)
        if url_m:
            return {"tool": "url_metadata", "args": {"url": url_m.group(1)}}

    # --- web_fetch (must have http URL AND "fetch" or "download" or "get content") ---
    url = _extract_url(prompt)
    if url:
        if any(w in p for w in ["fetch", "download", "get the content", "get content from",
                                 "get the page", "get url", "get page", "raw html"]):
            return {"tool": "web_fetch", "args": {"url": url}}
        # URL present but ambiguous (could be api_call, web_fetch, url_metadata)
        # Let Needle handle it

    # --- web_search (must say "search the web" or "search for" or "google") ---
    search_keywords = ["search the web", "search the internet", "search for",
                       "google", "find information about", "look up"]
    if any(kw in p for kw in search_keywords):
        # Extract query — remove the trigger phrase
        query = prompt
        for trigger in ["search the web for", "search the internet for",
                        "search for", "google", "find information about", "look up"]:
            if trigger in query.lower():
                idx = query.lower().find(trigger) + len(trigger)
                query = query[idx:].strip(" .?")
                break
        if query and len(query) > 2:
            return {"tool": "web_search", "args": {"query": query}}

    # --- api_call (must say "api" AND have URL, or "http get/post") ---
    if url and any(w in p for w in ["api", "http request", "http get", "http post",
                                     "rest api", "make a get request", "make a post request"]):
        method = "POST" if any(w in p for w in ["post", "put", "update"]) else "GET"
        return {"tool": "api_call", "args": {"url": url, "method": method}}


    # --- rag_list (clear phrases) ---
    if any(kw in p for kw in ["list rag documents", "list all documents in my rag",
                               "show knowledge base", "list documents in rag"]):
        return {"tool": "rag_list", "args": {}}

    # --- sql_sandbox_list ---
    if any(kw in p for kw in ["list sql sandbox", "list all sql sandbox",
                               "list my sql sandbox", "show sql sandbox"]):
        return {"tool": "sql_sandbox_list", "args": {}}

    # --- webhook_delete ---
    if any(kw in p for kw in ["delete webhook", "remove webhook"]):
        import re as _re_wd
        m = _re_wd.search(r'(?:delete|remove)\s+webhook\s+(wh_[a-zA-Z0-9_]+)', prompt, _re_wd.IGNORECASE)
        if m:
            return {"tool": "webhook_delete", "args": {"token": m.group(1)}}
        return None

    # --- webhook_events ---
    if any(kw in p for kw in ["webhook events", "events for webhook"]):
        import re as _re_we
        m = _re_we.search(r'(?:for|webhook)\s+(wh_[a-zA-Z0-9_]+)', prompt, _re_we.IGNORECASE)
        if m:
            args = {"token": m.group(1)}
            # Extract optional limit: "limit 5" / "top 10"
            lm = _re_we.search(r'(?:limit|top)\s+(\d+)', prompt, _re_we.IGNORECASE)
            if lm:
                args["limit"] = int(lm.group(1))
            return {"tool": "webhook_events", "args": args}
        return None

    # --- webhook_list ---
    if any(kw in p for kw in ["list my webhook", "list all webhook", "show my webhook"]):
        return {"tool": "webhook_list", "args": {}}

    # --- schedule_delete ---
    if any(kw in p for kw in ["delete scheduled task", "remove schedule", "delete schedule"]):
        import re as _re_sd
        m = _re_sd.search(r'(?:delete|remove)\s+(?:scheduled?\s+)?(?:task|schedule)\s+(?:named\s+)?([a-z_][a-z0-9_]*)', prompt, _re_sd.IGNORECASE)
        if m:
            return {"tool": "schedule_delete", "args": {"name": m.group(1)}}
        return None

    # --- schedule_run_now ---
    if any(kw in p for kw in ["run schedule", "trigger schedule", "run scheduled task now"]):
        import re as _re_sr
        m = _re_sr.search(r'(?:run|trigger)\s+(?:scheduled?\s+)?(?:task|schedule)\s+(?:named\s+)?([a-z_][a-z0-9_]*)', prompt, _re_sr.IGNORECASE)
        if m:
            return {"tool": "schedule_run_now", "args": {"name": m.group(1)}}
        return None

    # --- schedule_list ---
    if any(kw in p for kw in ["list my schedule", "list all schedule", "show my scheduled",
                               "show me my scheduled", "list schedules", "show schedules",
                               "list tasks", "show tasks", "what schedules", "my schedules"]):
        return {"tool": "schedule_list", "args": {}}

    # --- email_list_sent ---
    if any(kw in p for kw in ["list sent emails", "show sent emails", "my sent emails",
                               "recent sent emails", "what emails have i sent", "sent emails"]):
        import re as _re_els
        m = _re_els.search(r'(?:list|show|get|my|last|recent)\s+(\d+)\s+sent\s+emails?', prompt, _re_els.IGNORECASE)
        args = {}
        if m:
            args["limit"] = int(m.group(1))
        return {"tool": "email_list_sent", "args": args}

    # --- email_configured ---
    if any(kw in p for kw in ["email configured", "is my email", "check email setup",
                               "email setup", "is email set up", "do i have email configured",
                               "email status", "is my email working"]):
        return {"tool": "email_configured", "args": {}}

    # --- kpi_watch_add ---
    if any(kw in p for kw in ["alert me when", "create kpi watch", "add kpi watch", "watch kpi"]):
        import re as _re_kpi
        m = _re_kpi.search(
            r'(?:alert me when|create kpi watch|add kpi watch|watch kpi)\s+'
            r'([a-z_][a-z0-9_]*)\s*(<|>|<=|>=|==|!=)\s*(\d+(?:\.\d+)?)',
            prompt, _re_kpi.IGNORECASE
        )
        if m:
            kpi_name = m.group(1)
            op = m.group(2)
            threshold = float(m.group(3))
            comp_map = {"<": "lt", ">": "gt", "<=": "le", ">=": "ge", "==": "eq", "!=": "ne"}
            comparison = comp_map.get(op, "lt")
            check_prompt = f"What is the current {kpi_name}?"
            return {
                "tool": "kpi_watch_add",
                "args": {
                    "kpi_name": kpi_name,
                    "check_prompt": check_prompt,
                    "comparison": comparison,
                    "threshold_value": threshold,
                }
            }
        return None

    # --- kpi_watch_list ---
    if any(kw in p for kw in ["list kpi", "my kpi", "show kpi", "kpi watches", "what kpis"]):
        return {"tool": "kpi_watch_list", "args": {}}

    # --- kpi_watch_run ---
    if any(kw in p for kw in ["run kpis", "run all kpis", "check kpis now",
                               "run kpi watches", "trigger kpis", "check kpis"]):
        return {"tool": "kpi_watch_run", "args": {}}


    # --- Stats tools (Part 725) ---
    import re as _re_stats

    # data_stats (mean/median/std of a list)
    _stats_match = _re_stats.search(
        r"(?:mean|median|average|std|stddev|standard deviation|min|max|stats|statistics)\s+(?:of\s+)?\[([\d\.,\s\-]+)\]",
        prompt, _re_stats.IGNORECASE
    )
    if _stats_match:
        try:
            _vals = [float(x.strip()) for x in _stats_match.group(1).split(",") if x.strip()]
            if _vals:
                return {"tool": "data_stats", "args": {"values": _vals}}
        except Exception:
            pass

    # data_describe
    _desc_match = _re_stats.search(
        r"describe\s+([\w\-\.]+\.(?:csv|xlsx?|xls))",
        prompt, _re_stats.IGNORECASE
    )
    if _desc_match:
        return {"tool": "data_describe", "args": {"filename": _desc_match.group(1)}}

    # data_correlation
    _corr_match = _re_stats.search(
        r"correlation\s+between\s+(?:column\s+)?['\"]?(\w+)['\"]?\s+and\s+['\"]?(\w+)['\"]?\s+in\s+([\w\-\.]+\.(?:csv|xlsx?|xls))",
        prompt, _re_stats.IGNORECASE
    )
    if _corr_match:
        return {"tool": "data_correlation", "args": {"col_x": _corr_match.group(1), "col_y": _corr_match.group(2), "filename": _corr_match.group(3)}}

    # csv_groupby
    _grp_match = _re_stats.search(
        r"group\s+([\w\-\.]+\.(?:csv|xlsx?|xls))\s+by\s+['\"]?(\w+)['\"]?\s+(?:and\s+)?(sum|mean|count|min|max)\s+['\"]?(\w+)['\"]?",
        prompt, _re_stats.IGNORECASE
    )
    if _grp_match:
        return {"tool": "csv_groupby", "args": {"filename": _grp_match.group(1), "group_col": _grp_match.group(2), "agg_func": _grp_match.group(3).lower(), "agg_col": _grp_match.group(4)}}

    # --- Batch 1 tools (v1.3.0 Part 725) ---
    import re as _re_b1

    # list_files (supports kind=sandbox/workspace OR subpath)
    _lf_m = _re_b1.search(
        r"\b(?:list|show)\s+(?:all\s+)?(?:the\s+)?(?:files|sandbox files|workspace files)\b(?:\s+(?:in|under|inside|within)\s+([\w\-./\\]+))?",
        prompt, _re_b1.IGNORECASE
    )
    if _lf_m:
        args = {}
        subpath = (_lf_m.group(1) or "").strip()
        if subpath:
            low = subpath.lower()
            if low == "sandbox":
                args["kind"] = "sandbox"
            elif low == "workspace":
                args["kind"] = "workspace"
            else:
                args["path"] = subpath
        return {"tool": "list_files", "args": args}

    # web_search (only when explicitly asking to search the web)
    _search_m = _re_b1.search(r"\b(?:search|google|look up)\s+(?:the\s+)?(?:web\s+)?(?:for\s+)?(.+)", prompt, _re_b1.IGNORECASE)
    if _search_m and any(w in prompt.lower() for w in ("web", "google", "internet", "online")):
        return {"tool": "web_search", "args": {"query": _search_m.group(1).strip()}}

    # web_fetch
    _fetch_m = _re_b1.search(r"(?:fetch|get|download|read)\s+(?:the\s+)?(?:page\s+)?(https?://\S+)", prompt, _re_b1.IGNORECASE)
    if _fetch_m:
        return {"tool": "web_fetch", "args": {"url": _fetch_m.group(1)}}

    # email_configured
    if _re_b1.search(r"\b(?:is\s+)?email\s+(?:configured|setup|ready|working)\b", prompt, _re_b1.IGNORECASE):
        return {"tool": "email_configured", "args": {}}

    # email_send
    _em_m = _re_b1.search(r"send\s+(?:an?\s+)?email\s+to\s+(\S+@\S+)(?:\s+(?:about|saying|with subject)\s+(.+))?", prompt, _re_b1.IGNORECASE)
    if _em_m:
        return {"tool": "email_send", "args": {"to": _em_m.group(1), "subject": (_em_m.group(2) or "Message from Sunnyware").strip()[:100], "body": _em_m.group(2) or "Sent from Sunnyware"}}


    # --- edit_tableau_field ---
    m = re.search(r"(?:edit|update|change|modify)\s+(?:the\s+)?(?:tableau\s+)?(?:field|calc|calculation|filter|parameter)\s+['\"]?(.+?)['\"]?\s+(?:to|as)\s+['\"]?(.+?)['\"]?(?:\s+in\s+([\w\-\.]+\.twbx?))?", prompt, re.IGNORECASE)
    if m:
        return {"tool": "edit_tableau_field", "args": {"field_name": m.group(1).strip(), "new_value": m.group(2).strip(), "filename": m.group(3) or "workbook.twb"}}

    # --- read_bi_file (inspect Office/BI files) ---
    # Longest extensions first to avoid truncation (xlsm before xls, twbx before twb)
    _bi_ext = r"(?:xlsx|xlsm|xls|docx|pptx|pptx|pbix|twbx|twb|doc|ppt)"
    _bi_verbs = r"(?:read|show|inspect|analyze|open|view|summarize|describe|list|display|check)"
    # Capture only the LAST filename-like token (no spaces) to avoid grabbing preceding words
    _bi_match = _re_bi.search(
        r"(?:" + _bi_verbs + r"|what'?s in|tell me about|look at|contents of)\s+"
        r"(?:[^'\x22]*?\s)?"
        r"['\"]?([\w.\-]+\.(?:" + _bi_ext + r"))['\"]?",
        prompt, _re_bi.IGNORECASE
    )
    if _bi_match:
        _fname = (_bi_match.group(1) or "").strip()
        if _fname:
            _kind = "workspace"
            if "sandbox" in _p_low_bi:
                _kind = "sandbox"
            return {"tool": "read_bi_file", "args": {"file": _fname, "kind": _kind}}

    # Bare BI filename without explicit verb: only for BI extensions (.pbix/.twb/.twbx)
    _bare_bi = _re_bi.search(r"([\w.\-]+\.(?:pbix|twbx|twb))", prompt, _re_bi.IGNORECASE)
    if _bare_bi:
        _kind = "workspace"
        if "sandbox" in _p_low_bi:
            _kind = "sandbox"
        return {"tool": "read_bi_file", "args": {"file": _bare_bi.group(1).strip(), "kind": _kind}}

    
    # --- python_eval (must have "python" AND code-like words) ---
    python_keywords = ["run this python", "execute code", "use python to",
                       "run python", "run this code", "execute this code"]
    if any(kw in p for kw in python_keywords):
        # Extract code from the prompt
        import re as _re
        code_match = _re.search(r"(?:code:|run:|execute:)\s*(.+)", prompt, _re.IGNORECASE | _re.DOTALL)
        if code_match:
            return {"tool": "python_eval", "args": {"code": code_match.group(1).strip()}}
        return None  # can't extract code safely

    # (csv_query handled earlier at line ~170)

    # --- excel_write (Excel + write data) ---
    if "excel" in p and any(w in p for w in ["write", "save", "create"]):
        fname = _extract_filename(prompt, ["xlsx"])
        if fname:
            return None  # Need data extraction

    # --- chart_from_data (chart/plot/graph + numbers) ---
    if any(kw in p for kw in ["chart ", "plot ", "graph ", "bar chart", "line chart", "pie chart",
                               "create a chart", "make a chart", "plot data", "visualize numbers",
                               "histogram", "donut chart", "scatter plot"]):
        import re as _re_ch
        nums = _re_ch.findall(r'-?\d+(?:\.\d+)?', prompt)
        if len(nums) >= 2:
            import json as _json
            data = [float(n) if '.' in n else int(n) for n in nums]
            # Detect chart type
            chart_type = "line"
            if "bar" in p or "histogram" in p:
                chart_type = "bar"
            elif "pie" in p or "donut" in p:
                chart_type = "pie"
            elif "scatter" in p:
                chart_type = "line"  # fallback
            return {"tool": "chart_from_data", "args": {"data": _json.dumps(data), "chart_type": chart_type}}
        # No numbers detected — let LLM handle
        return None


    # --- insurance_data (simple actions) ---
    if any(kw in p for kw in ["insurance data states", "list insurance states", "which insurance states"]):
        return {"tool": "insurance_data", "args": {"action": "states"}}

    if any(kw in p for kw in ["insurance data discover", "discover insurance data", "find insurance dataset"]):
        import re as _re_id
        m = _re_id.search(r'(?:discover insurance data|find insurance dataset|insurance data discover)\s+(.+)', prompt, _re_id.IGNORECASE)
        if m:
            return {"tool": "insurance_data", "args": {"action": "discover", "query": m.group(1).strip()}}
        return None

    # --- insurance_research (simple actions) ---
    if any(kw in p for kw in ["insurance research filings", "search insurance filings", "insurance sec filings"]):
        import re as _re_ir
        m = _re_ir.search(r'(?:insurance research filings|search insurance filings|insurance sec filings)\s+(.+)', prompt, _re_ir.IGNORECASE)
        if m:
            return {"tool": "insurance_research", "args": {"action": "search_filings", "query": m.group(1).strip()}}
        return None

    if any(kw in p for kw in ["insurance fred search", "fred insurance search"]):
        import re as _re_if
        m = _re_if.search(r'(?:insurance fred search|fred insurance search)\s+(.+)', prompt, _re_if.IGNORECASE)
        if m:
            return {"tool": "insurance_research", "args": {"action": "fred_search", "query": m.group(1).strip()}}
        return None

    if any(kw in p for kw in ["insurance fred series", "fred insurance series"]):
        import re as _re_is
        m = _re_is.search(r'(?:insurance fred series|fred insurance series)\s+([A-Z0-9]+)', prompt, _re_is.IGNORECASE)
        if m:
            return {"tool": "insurance_research", "args": {"action": "fred_series", "series_id": m.group(1).upper()}}
        return None

    # --- finnhub_quote ---
    if any(kw in p for kw in ["stock quote for", "get quote for", "price of stock", "quote for"]):
        import re as _re_fq
        m = _re_fq.search(r'(?:stock quote for|get quote for|price of|quote for)\s+([A-Z]{1,5})', prompt)
        if m:
            return {"tool": "finnhub_quote", "args": {"action": "quote", "symbol": m.group(1)}}
        return None

    # --- fmp_fundamentals ---
    if any(kw in p for kw in ["income statement for", "balance sheet for", "cash flow for",
                               "financial ratios for", "key metrics for", "dcf for"]):
        import re as _re_fmp
        action = "income"
        if "balance" in p: action = "balance"
        elif "cash flow" in p: action = "cashflow"
        elif "ratios" in p: action = "ratios"
        elif "key metrics" in p: action = "metrics"
        elif "dcf" in p: action = "dcf"
        m = _re_fmp.search(r'(?:income statement for|balance sheet for|cash flow for|financial ratios for|key metrics for|dcf for)\s+([A-Z]{1,5})', prompt)
        if m:
            return {"tool": "fmp_fundamentals", "args": {"action": action, "ticker": m.group(1)}}
        return None

    # --- research_search (must have "research" or "investigate", not delegate) ---
    if any(kw in p for kw in ["research the topic", "investigate topic",
                               "do research", "deep research",
                               "research ", "investigate "]) and not any(kw in p for kw in ["delegate", "agent:", "sub-agent"]):


        # Extract query
        import re as _re
        q_match = _re.search(r"(?:research the topic of|research|investigate)\s+(.+)$", prompt, _re.IGNORECASE)
        if q_match:
            query = q_match.group(1).strip().strip("\"'")
            if query:
                return {"tool": "research_search", "args": {"query": query}}
        return None

    # --- document_diff (compare/diff X and Y) ---
    if any(kw in p for kw in ["compare two documents", "diff the", "compare documents",
                               "what changed between", "compare ", "diff ", "difference between"]):
        import re as _re_df
        # Find two filenames with extensions
        files = _re_df.findall(r'([\w\-.]+\.(?:txt|pdf|docx?|md|csv))', prompt, _re_df.IGNORECASE)
        if len(files) >= 2:
            return {"tool": "document_diff", "args": {"left_file": files[0], "right_file": files[1]}}
        # No two files detected — let LLM handle
        return None

    # --- html_to_text ---
    if any(kw in p for kw in ["convert html", "html to text", "strip html",
                               "extract text from html", "convert to text"]):
        import re as _re_ht
        url_m = _re_ht.search(r"(https?://[^\s]+)", prompt)
        if url_m:
            return {"tool": "html_to_text", "args": {"url": url_m.group(1)}}
        return None  # No URL — LLM handles (user may paste raw HTML)

    # --- pdf_report ---
    if "pdf" in p and any(w in p for w in ["create", "generate", "make", "build", "write", "report"]):
        return None  # Need title/content extraction

    # --- kpi_watch_add ---
    if any(kw in p for kw in ["add a kpi", "watch metric", "monitor number",
                               "add kpi watch"]):
        return None  # Need KPI name extraction

    # --- hitl_config_update ---
    if any(kw in p for kw in ["set hitl", "require confirmation", "configure hitl",
                               "hitl config", "auto-approve", "auto approve"]):
        import re as _re_htl
        # Extract tool name — look for common tool name patterns
        tool_m = _re_htl.search(
            r"(?:set hitl|configure hitl|require confirmation|hitl config|auto-approve|auto approve)"
            r"\s+(?:(?:for|on|to)\s+)?([a-z_][a-z0-9_]*[a-z0-9])",
            prompt, _re_htl.IGNORECASE
        )
        if not tool_m:
            return None
        tool_name = tool_m.group(1).strip()
        # Determine decision based on trigger
        if any(kw in p for kw in ["auto-approve", "auto approve", "allow", "auto"]):
            decision = "auto"
        else:
            decision = "require"
        return {"tool": "hitl_config_update", "args": {
            "tool_name": tool_name,
            "decision": decision,
        }}


    # --- webhook_add (create/add webhook) ---
    if any(kw in p for kw in ["create a webhook", "add a webhook", "set up webhook",
                               "create webhook", "add webhook"]):
        import re as _re_wh
        name_m = _re_wh.search(r"(?:named|called)\s+[\"\']?([\w\- ]+?)[\"\']?(?:\s|$)", prompt, _re_wh.IGNORECASE)
        if not name_m:
            name_m = _re_wh.search(r"webhook\s+[\"\']?([\w\-]+)[\"\']?", prompt, _re_wh.IGNORECASE)
        if name_m:
            name = name_m.group(1).strip()
            return {"tool": "webhook_add", "args": {"name": name}}
        return None  # No name detected — LLM handles

    # --- schedule_add ---
    if any(kw in p for kw in ["schedule a task", "schedule task", "set reminder",
                               "recurring job", "schedule every"]):
        import re as _re_sa
        # Extract name (after "named" or "called" or "for")
        name_m = _re_sa.search(r'(?:named|called|for)\s+["\']?([a-z_][a-z0-9_]*)["\']?', prompt, _re_sa.IGNORECASE)
        if not name_m:
            return None  # No name detected — LLM handles
        name = name_m.group(1).strip()
        # Extract interval: "every 60 seconds" / "every hour" / "every 5 minutes" / "every day"
        interval = 3600  # default 1 hour
        im = _re_sa.search(r'every\s+(\d+)?\s*(seconds?|minutes?|hours?|days?)', prompt, _re_sa.IGNORECASE)
        if im:
            val = int(im.group(1)) if im.group(1) else 1
            unit = im.group(2).lower()
            if unit.startswith('second'): interval = val
            elif unit.startswith('minute'): interval = val * 60
            elif unit.startswith('hour'): interval = val * 3600
            elif unit.startswith('day'): interval = val * 86400
        # Extract prompt: everything after the interval phrase
        # Build agent prompt by removing the interval phrase from the original prompt
        agent_prompt = _re_sa.sub(r'(?:every\s+(?:\d+\s*)?(?:seconds?|minutes?|hours?|days?))\b', '', prompt, flags=_re_sa.IGNORECASE).strip()
        return {"tool": "schedule_add", "args": {
            "name": name,
            "prompt": agent_prompt,
            "interval_seconds": interval,
        }}

    # --- document_library (list action only; add/save needs LLM) ---
    if any(w in p for w in ["list library", "list documents", "show library documents",
                              "list my documents", "list saved documents", "show my documents"]):
        return {"tool": "document_library", "args": {"action": "list"}}

    # --- search_library (library-related search) ---
    if "library" in p and any(w in p for w in ["find", "search", "related to"]):
        import re as _re_sl
        patterns = [
            r"search\s+(?:in\s+)?(?:the\s+)?library\s+for\s+(.+)",
            r"find\s+(.+?)\s+in\s+(?:the\s+)?library",
            r"related to\s+(.+?)(?:\s+in\s+(?:the\s+)?library)?$",
            r"(?:find|search|related to)\s+(.+)",
        ]
        query = None
        for pat in patterns:
            m = _re_sl.search(pat, prompt, _re_sl.IGNORECASE)
            if m:
                q = m.group(1).strip()
                q = _re_sl.sub(r"\s+in\s+(?:the\s+)?library\s*$", "", q, flags=_re_sl.IGNORECASE)
                q = q.strip()
                if q:
                    query = q
                    break
        if query:
            return {"tool": "search_library", "args": {"query": query}}
        return None
        return None

    # --- rag_search (RAG database search) ---
    if "rag" in p and any(w in p for w in ["search", "find", "database"]):
        import re as _re_rs
        patterns = [
            r"(?:search|query)\s+(?:in\s+)?(?:the\s+)?rag(?:\s+database)?\s+for\s+(.+)",
            r"find\s+(.+?)\s+in\s+(?:the\s+)?rag(?:\s+database)?",
            r"(?:search|find|query)\s+(?:in\s+)?(?:the\s+)?rag(?:\s+database)?\s+(.+)",
        ]
        query = None
        for pat in patterns:
            m = _re_rs.search(pat, prompt, _re_rs.IGNORECASE)
            if m:
                q = m.group(1).strip()
                q = _re_rs.sub(r"\s+in\s+(?:the\s+)?rag(?:\s+database)?\s*$", "", q, flags=_re_rs.IGNORECASE)
                q = q.strip()
                if q:
                    query = q
                    break
        if query:
            return {"tool": "rag_search", "args": {"query": query}}
        return None
        return None

    # Fix plural bugs: "list all my sql sandboxes" and "list all my webhooks"
    if "list all my sql sandbox" in p or "list my sql sandboxes" in p or "show my sql sandboxes" in p:
        return {"tool": "sql_sandbox_list", "args": {}}
    
    if "list all my webhook" in p or "list my webhooks" in p or "show my webhooks" in p:
        return {"tool": "webhook_list", "args": {}}
    
    if "list my scheduled" in p or "list all my scheduled" in p or "show my scheduled" in p:
        return {"tool": "schedule_list", "args": {}}

    # --- workspace_snapshot ---
    if any(kw in p for kw in ["workspace snapshot", "snapshot workspace",
                               "zip the workspace", "archive the workspace",
                               "snapshot of the workspace"]):
        import re as _re_ws
        m = _re_ws.search(
            r'(?:workspace snapshot|snapshot workspace|zip the workspace|archive the workspace|snapshot of the workspace)'
            r'(?:\s+(?:of|for)\s+([\w\-./\\]+))?',
            prompt, _re_ws.IGNORECASE
        )
        args = {}
        if m and m.group(1):
            args["subpath"] = m.group(1).strip()
        return {"tool": "workspace_snapshot", "args": args}

    # --- clause_extractor (list_types action only) ---
    if any(kw in p for kw in ["list clause types", "what clause types", "available clause types"]):
        return {"tool": "clause_extractor", "args": {"action": "list_types"}}

    # --- legal_citation_check (verify citation) ---
    if any(kw in p for kw in ["verify citation", "check citation", "validate citation"]):
        import re as _re_lc
        # Pattern: volume reporter page, e.g., 576 U.S. 644
        m = _re_lc.search(r'(\d+)\s+([A-Za-z.]+)\s+(\d+)', prompt)
        if m:
            return {
                "tool": "legal_citation_check",
                "args": {
                    "action": "verify_one",
                    "volume": m.group(1),
                    "reporter": m.group(2),
                    "page": m.group(3),
                }
            }
        return None

    # No confident keyword match — let Needle 3 handle it
    return None
