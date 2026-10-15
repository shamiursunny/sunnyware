# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 127: earnings-call transcript summarizer.

AlphaSense-inspired but fully deterministic: given raw transcript
text, slice it into themed sections (revenue, margin, guidance,
capex, risk, capital returns), pull the most-relevant sentences per
theme, and score overall sentiment (reuses Part 121's lexicon).

No LLM, no network, no external calls.
"""
import re

from ._sentiment import score_text

_SENT_RE = re.compile(r"(?<=[.!?])\s+")

_THEMES = {
    "revenue": [
        "revenue", "revenues", "sales", "top line", "top-line",
        "bookings", "orders", "arpu",
    ],
    "margin": [
        "margin", "margins", "gross margin", "operating margin",
        "profitability", "profit", "eps", "earnings per share",
    ],
    "guidance": [
        "guidance", "outlook", "forecast", "expect", "expects",
        "expected", "anticipate", "anticipates", "we project",
        "for the full year", "next quarter", "back half",
    ],
    "capex": [
        "capex", "capital expenditure", "capital expenditures",
        "investment", "investments", "spend", "spending", "buyback",
        "share repurchase", "repurchases",
    ],
    "risk": [
        "risk", "risks", "headwind", "headwinds", "uncertainty",
        "challenging", "difficult", "softer", "softness", "pressure",
        "decline", "declined", "impairment", "downturn", "litigation",
    ],
    "capital_returns": [
        "dividend", "dividends", "buyback", "buybacks",
        "share repurchase", "share repurchases", "return of capital",
        "return cash", "capital return",
    ],
    "operations": [
        "headcount", "hiring", "restructuring", "cost reduction",
        "supply chain", "capacity", "utilization", "efficiency",
        "productivity", "operational",
    ],
    "demand": [
        "demand", "pipeline", "backlog", "customer", "customers",
        "win", "wins", "won", "renewals", "churn", "churn rate",
    ],
}


def _split_sentences(text):
    if not text:
        return []
    # Normalize whitespace
    t = re.sub(r"\s+", " ", text).strip()
    # Split on sentence boundaries
    parts = _SENT_RE.split(t)
    return [s.strip() for s in parts if len(s.strip()) >= 30]


def _theme_score(sentence, terms):
    """Score = count of theme terms in the sentence (case-insensitive)."""
    s = sentence.lower()
    score = 0
    for t in terms:
        if " " in t:
            score += s.count(t)
        else:
            # word-boundary for single words
            score += len(re.findall(r"\b" + re.escape(t) + r"\b", s))
    return score


def summarize_transcript(text, max_per_theme=3, min_sentences=4):
    if not isinstance(text, str) or not text.strip():
        return {"error": "transcript is empty",
                "themes": {}, "sentiment": None}

    sentences = _split_sentences(text)
    if len(sentences) < min_sentences:
        return {"error": "transcript too short (need >= "
                         + str(min_sentences) + " sentences)",
                "sentences_found": len(sentences),
                "themes": {}, "sentiment": None}

    themes = {}
    for name, terms in _THEMES.items():
        scored = []
        for s in sentences:
            sc = _theme_score(s, terms)
            if sc > 0:
                scored.append((sc, s))
        scored.sort(key=lambda x: (-x[0], -len(x[1])))
        top = [{"score": sc, "sentence": sent}
               for sc, sent in scored[:max_per_theme]]
        themes[name] = {
            "mentions": len(scored),
            "top": top,
        }

    sentiment = score_text(text)

    return {
        "sentence_count": len(sentences),
        "char_count": len(text),
        "sentiment": sentiment,
        "themes": themes,
        "themes_covered": sorted(
            k for k, v in themes.items() if v["mentions"] > 0
        ),
    }


class EarningsCallTool:
    name = "earnings_call"
    description = (
        "Summarize an earnings-call transcript (raw text). Splits into "
        "themes (revenue, margin, guidance, capex, risk, capital_returns, "
        "operations, demand), pulls the top sentences per theme, and "
        "scores overall sentiment using the Part 121 lexicon. Pure "
        "Python, deterministic, no LLM, no network."
    )
    parameters = {
        "transcript": {
            "type": "string",
            "description": "Raw transcript text (prepared remarks + Q&A OK)",
            "required": True,
        },
        "max_per_theme": {
            "type": "integer",
            "description": "Max sentences per theme (default 3, max 10)",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        text = args.get("transcript")
        if not isinstance(text, str) or not text.strip():
            return {"error": "transcript is required (raw text)"}
        try:
            mx = int(args.get("max_per_theme") or 3)
        except Exception:
            mx = 3
        mx = max(1, min(mx, 10))
        try:
            return summarize_transcript(text, max_per_theme=mx)
        except Exception as e:
            return {"error": type(e).__name__ + ": " + str(e)}
