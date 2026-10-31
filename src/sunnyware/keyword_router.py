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
    math_match = re.search(r'(\d+\s*[\+\-\*/\*\*]+\s*\d+[\d\s\+\-\*/\*\*]*?)', prompt)
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
    """
    Match obvious tool intent using keywords and regex extraction.
    Returns {"tool": name, "args": {...}} or None.
    """
    p = prompt.lower()

    # --- Math regex (catches '2+2' etc.) ---
    import re as _re
    _math_match = _re.search(r'(?:what is|calculate|compute|evaluate)?\s*(-?\d+(?:\.\d+)?\s*[\+\-\*\/\%\^]\s*-?\d+(?:\.\d+)?(?:\s*[\+\-\*\/\%\^]\s*-?\d+(?:\.\d+)?)*)', prompt.lower())
    if _math_match:
        expr = _math_match.group(1).strip()
        if all(c in '0123456789+-*/%^() .' for c in expr):
            return {"tool": "calculator", "args": {"expression": expr}}

# --- calculator ---
    calc_keywords = ["calculate", "compute", "math", "square root", "sqrt",
                     "multiply", "divide", "what is", "how much is"]
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
            return {"tool": "email_send", "args": {
                "to": to_match.group(1),
                "subject": subject,
                "body": prompt,
            }}


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

    # --- list_files ---
    if any(kw in p for kw in ["list files", "show files", "what files", "workspace files", "list workspace"]):
        return {"tool": "list_files", "args": {}}

    # --- pdf_read (must have .pdf extension, and not be a compare/diff prompt) ---
    if ".pdf" in p and not any(kw in p for kw in ["create", "generate", "make", "build", "write a pdf", "compare", "diff"]):
        fname = _extract_filename(prompt, ["pdf"])
        if fname:
            return {"tool": "pdf_read", "args": {"file": fname}}

    # --- excel_read (must have .xlsx) ---
    if "excel" in p or ".xlsx" in p:
        fname = _extract_filename(prompt, ["xlsx"])
        if fname:
            action = "write" if any(w in p for w in ["write", "save", "create"]) else "read"
            if action == "read":
                return {"tool": "excel_read", "args": {"file": fname}}
            # write needs structured data (sheets array) — let LLM handle
            return None

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

    # --- read_file (must have .txt) ---
    if ".txt" in p:
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

    # --- list_files (clear phrases) ---
    if any(kw in p for kw in ["list files", "list the files", "what files are",
                               "show me the files", "show the files"]):
        return {"tool": "list_files", "args": {}}

    # --- rag_list (clear phrases) ---
    if any(kw in p for kw in ["list rag documents", "list all documents in my rag",
                               "show knowledge base", "list documents in rag"]):
        return {"tool": "rag_list", "args": {}}

    # --- sql_sandbox_list ---
    if any(kw in p for kw in ["list sql sandbox", "list all sql sandbox",
                               "list my sql sandbox", "show sql sandbox"]):
        return {"tool": "sql_sandbox_list", "args": {}}

    # --- webhook_list ---
    if any(kw in p for kw in ["list my webhook", "list all webhook", "show my webhook"]):
        return {"tool": "webhook_list", "args": {}}

    # --- schedule_list ---
    if any(kw in p for kw in ["list my schedule", "list all schedule", "show my scheduled",
                               "show me my scheduled", "list schedules", "show schedules",
                               "list tasks", "show tasks", "what schedules", "my schedules"]):
        return {"tool": "schedule_list", "args": {}}

    # --- email_configured ---
    if "email configured" in p or "is my email" in p:
        return {"tool": "email_configured", "args": {}}

    # --- kpi_watch_list ---
    if any(kw in p for kw in ["list kpi", "my kpi", "show kpi", "kpi watches", "what kpis"]):
        return {"tool": "kpi_watch_list", "args": {}}

    # --- kpi_watch_run ---
    if any(kw in p for kw in ["run kpis", "run all kpis", "check kpis now",
                               "run kpi watches", "trigger kpis", "check kpis"]):
        return {"tool": "kpi_watch_run", "args": {}}


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
                               "create a chart", "make a chart", "plot data", "visualize numbers"]):
        import re as _re_ch
        nums = _re_ch.findall(r'-?\d+(?:\.\d+)?', prompt)
        if len(nums) >= 2:
            import json as _json
            data = [float(n) if '.' in n else int(n) for n in nums]
            # Detect chart type
            chart_type = "line"
            if "bar" in p:
                chart_type = "bar"
            elif "pie" in p:
                chart_type = "pie"
            return {"tool": "chart_from_data", "args": {"data": _json.dumps(data), "chart_type": chart_type}}
        # No numbers detected — let LLM handle
        return None

    # --- narrate_table (explicit "narrate" or "explain" table) ---
    if "narrate" in p and "table" in p:
        return None  # Need table extraction
    if "explain this table" in p or "describe this table" in p:
        return None

    # --- financial_metrics ---
    if "financial metrics" in p or "stock metrics" in p or "investment metrics" in p:
        return None

    # --- data_quality_report ---
    if "data quality report" in p or "quality check" in p or "check data quality" in p:
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
                               "hitl config"]):
        return None  # Need tool name extraction

    # --- recall_history ---
    if any(kw in p for kw in ["recall our last", "recall history", "remember last",
                               "what did we discuss"]):
        return None  # Need count extraction

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

    # --- schedule_add (schedule/create task) ---
    if any(kw in p for kw in ["schedule a task", "schedule task", "set reminder",
                               "recurring job", "schedule every"]):
        return None  # Need name/interval extraction

    # --- search_library (library-related search) ---
    if "library" in p and any(w in p for w in ["find", "search", "related to"]):
        return None  # Need query extraction

    # --- rag_search (RAG database search) ---
    if "rag" in p and any(w in p for w in ["search", "find", "database"]):
        return None  # Need query extraction

    # Fix plural bugs: "list all my sql sandboxes" and "list all my webhooks"
    if "list all my sql sandbox" in p or "list my sql sandboxes" in p or "show my sql sandboxes" in p:
        return {"tool": "sql_sandbox_list", "args": {}}
    
    if "list all my webhook" in p or "list my webhooks" in p or "show my webhooks" in p:
        return {"tool": "webhook_list", "args": {}}
    
    if "list my scheduled" in p or "list all my scheduled" in p or "show my scheduled" in p:
        return {"tool": "schedule_list", "args": {}}

    # No confident keyword match — let Needle 3 handle it
    return None
