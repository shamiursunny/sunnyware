# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""FP&A report generator — strict markdown, no hallucinations."""

from typing import List, Dict

SYSTEM_PROMPT = """You are an elite, certified Financial Planning & Analysis (FP&A) AI Agent.
Your task is to generate an Executive Variance Summary based strictly and exclusively
on the context snippets provided.

CRITICAL RULES:
1. NO HALLUCINATIONS. Do not invent any figure, date, or name not in the context.
   If a calculation is requested but data is missing, output: [Data Missing for X].
2. Variance = Actual - Budget.
   - Expenses: positive variance = Unfavorable (U); negative = Favorable (F).
   - Revenue:  positive variance = Favorable (F);  negative = Unfavorable (U).
3. Always cite sources as [source: <source name>, chunk <id>].
4. If any section has no data, output: [Data Missing]
"""


def build_context_block(chunks: List[Dict]) -> str:
    lines = []
    for c in chunks:
        src = c.get("source", "unknown")
        cid = c.get("chunk_id", "?")
        txt = c.get("text") or c.get("preview") or ""
        lines.append(f"[source: {src}, chunk {cid}]\n{txt}")
    return "\n\n".join(lines)


def build_prompt(question: str, chunks: List[Dict]) -> str:
    context = build_context_block(chunks)
    return f"""{SYSTEM_PROMPT}

RETRIEVED CONTEXT:
{context}

USER QUESTION:
{question}

Output the report now, following this exact markdown layout:

## EXECUTIVE FINANCIAL SUMMARY & VARIANCE REPORT
**Reporting Scope:** [State the PDF pages / spreadsheet rows / file meta detected]

### 1. Key Operational Variances
- **Account/Department:** [summary]
  - *Actual vs. Budget:* $X vs $Y
  - *Calculated Variance:* $Z (F) or (U)
  - *Contextual Driver:* [narrative if present]
  - *Citation:* [source: ..., chunk ...]

### 2. Isolated Anomalies & Audit Targets
- [...]

### 3. Immediate Action Items
- [...]
"""


def render_stub(question: str, chunks: List[Dict]) -> str:
    """Fallback markdown when no LLM is wired in (Part 31B-1 stub)."""
    scope = ", ".join(sorted({c.get("source", "?") for c in chunks})) or "(none)"
    lines = [
        "## EXECUTIVE FINANCIAL SUMMARY & VARIANCE REPORT",
        f"**Reporting Scope:** {scope}",
        "",
        "### 1. Key Operational Variances",
    ]
    if not chunks:
        lines.append("[Data Missing]")
    else:
        for c in chunks[:5]:
            src = c.get("source", "?")
            cid = c.get("chunk_id", "?")
            txt = (c.get("text") or c.get("preview") or "")[:200]
            lines.append(f"- {txt} [source: {src}, chunk {cid}]")
    lines += [
        "",
        "### 2. Isolated Anomalies & Audit Targets",
        "[Data Missing]",
        "",
        "### 3. Immediate Action Items",
        "[Data Missing]",
        "",
        "_(Report generated from retrieved context. Wire in the LLM to activate narrative generation.)_",
    ]
    return "\n".join(lines)


def status() -> dict:
    return {"system_prompt_chars": len(SYSTEM_PROMPT), "stub_renderer": True}


async def generate_narrative(
    question: str,
    chunks: list,
    model: str = None,
    timeout: float = 90.0,
) -> dict:
    """Call the configured LLM with the built prompt to produce a real FP&A report.

    Lazy-imports sunnyware.llm so this module stays usable without a live LLM.

    Returns:
      {"ok": True,  "narrative": "<markdown>", "model": "...", "latency_ms": N}
      {"ok": False, "error": "...", "fallback": "<stub markdown>", ...}
    """
    if not chunks:
        return {
            "ok": False,
            "error": "no chunks provided",
            "fallback": render_stub(question, chunks),
        }

    try:
        from .. import llm as llm_client
    except Exception as e:
        return {
            "ok": False,
            "error": "llm import failed: " + type(e).__name__ + ": " + str(e),
            "fallback": render_stub(question, chunks),
        }

    prompt = build_prompt(question, chunks)

    try:
        res = await llm_client.chat(prompt=prompt, model=model, timeout=timeout)
    except Exception as e:
        return {
            "ok": False,
            "error": "llm call raised: " + type(e).__name__ + ": " + str(e),
            "fallback": render_stub(question, chunks),
        }

    if not res.get("ok"):
        return {
            "ok": False,
            "error": res.get("error", "unknown llm error"),
            "fallback": render_stub(question, chunks),
            "latency_ms": res.get("latency_ms"),
        }

    content = (res.get("content") or "").strip()
    # Strip code fences the model may have wrapped around the report.
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = chr(10).join(lines).strip()
    if not content:
        return {
            "ok": False,
            "error": "empty llm response",
            "fallback": render_stub(question, chunks),
            "latency_ms": res.get("latency_ms"),
        }

    return {
        "ok": True,
        "narrative": content,
        "model": res.get("model"),
        "latency_ms": res.get("latency_ms"),
    }
