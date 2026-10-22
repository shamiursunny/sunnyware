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

    # --- pdf_read (must have .pdf extension) ---
    if "pdf" in p or ".pdf" in p:
        fname = _extract_filename(prompt, ["pdf"])
        if fname:
            return {"tool": "pdf_read", "args": {"filepath": fname}}

    # --- excel_read (must have .xlsx) ---
    if "excel" in p or ".xlsx" in p:
        fname = _extract_filename(prompt, ["xlsx"])
        if fname:
            action = "write" if any(w in p for w in ["write", "save", "create"]) else "read"
            tool = f"excel_{action}"
            if action == "read":
                return {"tool": tool, "args": {"filepath": fname}}
            # write needs data — fall through to LLM
            return None

    # --- csv_query (must have .csv) ---
    if ".csv" in p or "csv file" in p:
        fname = _extract_filename(prompt, ["csv"])
        if fname:
            # Let Needle extract the SQL query — it's too complex for regex
            return None

    # --- read_file (must have .txt) ---
    if ".txt" in p:
        fname = _extract_filename(prompt, ["txt"])
        if fname and any(w in p for w in ["read", "open", "contents", "show"]):
            return {"tool": "read_file", "args": {"filepath": fname}}

    # --- write_file (must have .txt) ---
    if any(w in p for w in ["write", "save", "create"]) and ".txt" in p:
        fname = _extract_filename(prompt, ["txt"])
        if fname:
            # Need content — let LLM handle it
            return None

    # --- web_fetch (must have http URL AND "fetch" or "download" or "get content") ---
    url = _extract_url(prompt)
    if url:
        if any(w in p for w in ["fetch", "download", "get the content", "get content from",
                                 "get the page", "raw html"]):
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
                               "show me my scheduled"]):
        return {"tool": "schedule_list", "args": {}}

    # --- email_configured ---
    if "email configured" in p or "is my email" in p:
        return {"tool": "email_configured", "args": {}}

    # --- kpi_watch_list ---
    if "list kpi" in p or "my kpi" in p:
        return {"tool": "kpi_watch_list", "args": {}}


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

    # --- csv_query (needs .csv + "query" / "select") ---
    if ".csv" in p and any(w in p for w in ["query", "select", "filter", "where"]):
        fname = _extract_filename(prompt, ["csv"])
        if fname:
            # Let Needle extract the SQL — too complex for regex
            return None

    # --- excel_write (Excel + write data) ---
    if "excel" in p and any(w in p for w in ["write", "save", "create"]):
        fname = _extract_filename(prompt, ["xlsx"])
        if fname:
            return None  # Need data extraction

    # --- chart_from_data (bar/line/pie chart triggers) ---
    if any(kw in p for kw in ["bar chart", "line chart", "pie chart",
                               "create a chart", "make a chart", "plot data",
                               "visualize numbers"]):
        return None  # Need data extraction

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

    # --- research_search (must have "research" or "investigate") ---
    if any(kw in p for kw in ["research the topic", "investigate topic",
                               "do research", "deep research"]):
        # Extract query
        import re as _re
        q_match = _re.search(r"(?:research the topic of|research|investigate)\s+(.+)$", prompt, _re.IGNORECASE)
        if q_match:
            query = q_match.group(1).strip().strip("\"'")
            if query:
                return {"tool": "research_search", "args": {"query": query}}
        return None

    # --- document_diff (must say "compare" or "diff") ---
    if any(kw in p for kw in ["compare two documents", "diff the", "compare documents",
                               "what changed between"]):
        return None  # Need doc extraction

    # --- html_to_text ---
    if any(kw in p for kw in ["convert html", "html to text", "strip html",
                               "extract text from html"]):
        return None  # Need HTML extraction

    # --- pdf_report ---
    if any(kw in p for kw in ["create a pdf report", "generate pdf", "make pdf report",
                               "create pdf report"]):
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
        return None  # Need name/URL extraction

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
