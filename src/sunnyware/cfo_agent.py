# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 191: CFO Agent — AI accountant with double-entry tool calling."""

import json
import os
from typing import Optional


SYSTEM_PROMPT = """You are "Sunnyware CFO", a meticulous, autonomous AI accountant embedded in the Sunnyware Admin Panel. Your job is to handle financial tasks with 100% accuracy using double-entry bookkeeping.

# CORE RULES (NON-NEGOTIABLE)
1. NEVER invent account names. ONLY use accounts from the `get_chart_of_accounts` tool output.
2. EVERY entry MUST balance: debit = credit (+tax on the debit side if applicable).
3. ALWAYS call `get_ledger_history` first when categorizing a new transaction.
4. NEVER post directly. ALWAYS call `create_draft_entry` first — the human approves it.
5. State your confidence (high/medium/low) and reasoning in the draft.
6. If the request is ambiguous (missing amount, date, or account), ASK a clarifying question — do NOT guess.
7. If debit/credit don't balance, refuse and explain.

# WORKFLOW
Step 1: Call `get_chart_of_accounts` to see valid accounts.
Step 2: Call `get_ledger_history` with a keyword to learn patterns.
Step 3: Determine debit and credit accounts from the COA.
Step 4: Call `create_draft_entry` with all fields populated.
Step 5: Reply: "Draft created — [description] — Debit [account] $X / Credit [account] $X. Confidence: [level]. Awaiting your approval."

# EXAMPLES
User: "Add a cost of $500 for Facebook ads today"
- Debit: Expenses:Marketing | Credit: Assets:Cash | Amount: 500
- Confidence: high

User: "Withdraw $1000 for owner draw"
- Debit: Equity:Owner Draws | Credit: Assets:Cash | Amount: 1000
- Confidence: high

User: "Paid $50 for lunch"
- Debit: Expenses:Meals | Credit: Assets:Cash | Amount: 50
- Confidence: medium

# TONE
Concise, no fluff. End with: "Awaiting your approval to post."
"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_chart_of_accounts",
            "description": "Return the full chart of accounts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ledger_history",
            "description": "Search past posted ledger entries by keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft_entry",
            "description": "Create a DRAFT journal entry for human approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "description": {"type": "string"},
                    "debit_account": {"type": "string"},
                    "credit_account": {"type": "string"},
                    "amount": {"type": "number"},
                    "tax_amount": {"type": "number"},
                    "tax_account": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["date", "description", "debit_account", "credit_account", "amount"],
            },
        },
    },
]


def _api_config() -> Optional[dict]:
    key = (os.getenv("CFO_LLM_API_KEY") or os.getenv("LLM_API_KEY")
           or os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    base = (os.getenv("CFO_LLM_BASE_URL") or os.getenv("LLM_BASE_URL")
            or "https://api.openai.com/v1").rstrip("/")
    model = (os.getenv("CFO_AGENT_MODEL") or os.getenv("LLM_MODEL")
             or "gpt-4o-mini").strip()
    return {"base": base, "key": key, "model": model}


def _execute_tool(name: str, args: dict) -> dict:
    from . import accounting_store as _acc
    try:
        if name == "get_chart_of_accounts":
            return _acc.get_chart_of_accounts()
        if name == "get_ledger_history":
            return {"entries": _acc.get_ledger_history(args.get("query", ""), int(args.get("limit", 10)))}
        if name == "create_draft_entry":
            draft = _acc.create_draft_entry(
                date=args.get("date", ""),
                description=args.get("description", ""),
                debit_account=args.get("debit_account", ""),
                credit_account=args.get("credit_account", ""),
                amount=float(args.get("amount", 0) or 0),
                tax_amount=float(args.get("tax_amount", 0) or 0),
                tax_account=args.get("tax_account", ""),
                confidence=args.get("confidence", "medium"),
                reasoning=args.get("reasoning", ""),
            )
            return {"ok": True, "draft": draft}
        return {"error": f"unknown tool: {name}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


async def handle_chat(message: str, history: list = None) -> dict:
    cfg = _api_config()
    if not cfg:
        return {
            "reply": "CFO Agent not configured. Add `LLM_API_KEY` to HF Secrets.",
            "drafts": [],
            "error": "no_llm_config",
        }

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in (history or []):
        role = h.get("role")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    created_drafts = []
    rounds_used = 0

    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as cli:
            for round_num in range(6):
                rounds_used = round_num + 1
                try:
                    r = await cli.post(
                        cfg["base"] + "/chat/completions",
                        headers={"Authorization": "Bearer " + cfg["key"], "Content-Type": "application/json"},
                        json={"model": cfg["model"], "messages": messages, "tools": TOOLS, "tool_choice": "auto", "temperature": 0.1},
                    )
                except Exception as e:
                    return {"reply": f"LLM call failed: {type(e).__name__}: {e}", "drafts": created_drafts, "error": "llm_network"}

                if r.status_code != 200:
                    return {"reply": f"LLM API error {r.status_code}: {r.text[:300]}", "drafts": created_drafts, "error": "llm_http"}

                data = r.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                tool_calls = msg.get("tool_calls") or []

                if not tool_calls:
                    return {"reply": msg.get("content") or "(no response)", "drafts": created_drafts, "rounds": rounds_used}

                messages.append(msg)
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args_raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                    except Exception:
                        args = {}
                    result = _execute_tool(name, args)
                    if name == "create_draft_entry" and result.get("draft", {}).get("id"):
                        created_drafts.append(result["draft"])
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": json.dumps(result)})

            return {"reply": "Agent hit max rounds (6). Try a simpler request.", "drafts": created_drafts, "error": "max_rounds"}

    except Exception as e:
        return {"reply": f"Agent error: {type(e).__name__}: {e}", "drafts": created_drafts, "error": "agent_exception"}


def status() -> dict:
    cfg = _api_config()
    return {
        "enabled": cfg is not None,
        "model": cfg["model"] if cfg else None,
        "base_url": cfg["base"] if cfg else None,
        "tools_count": len(TOOLS),
    }
