# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 121: lexicon-based sentiment scoring.

Pure Python. No LLM, no network, no external calls. Deterministic.
"""
import re

_POSITIVE = {
    "strong", "growth", "grew", "profit", "profitable", "improved",
    "improvement", "increase", "increased", "gains", "gain", "up",
    "outperform", "exceeded", "beat", "beats", "positive", "upside",
    "expansion", "expanded", "record", "highest", "best", "robust",
    "resilient", "recovery", "recovered", "healthy", "solid", "stable",
    "successful", "success", "opportunity", "opportunities", "confident",
    "confidence", "bullish", "optimistic", "upswing",
}

_NEGATIVE = {
    "weak", "weakness", "decline", "declined", "declining", "loss",
    "losses", "down", "downturn", "fall", "fell", "drop", "dropped",
    "underperform", "missed", "miss", "negative", "downside",
    "contraction", "contracted", "lowest", "worst", "concern",
    "concerns", "risk", "risks", "risky", "uncertain", "uncertainty",
    "volatile", "volatility", "bearish", "pessimistic", "warned",
    "warning", "headwind", "headwinds", "cut", "cuts", "deteriorate",
    "deteriorated", "deteriorating", "impairment", "default", "defaults",
    "defaulted", "lawsuit", "litigation", "investigation", "penalty",
    "penalties", "fine", "fined", "recall", "recalls", "downgrade",
    "downgraded",
}

_NEGATORS = {
    "not", "no", "never", "none", "without", "isn't", "aren't", "wasn't",
    "weren't", "doesn't", "don't", "didn't", "won't", "wouldn't",
    "shouldn't", "couldn't", "hardly", "barely", "scarcely",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]{1,40}")


def score_text(text: str, lookback: int = 2) -> dict:
    """Return lexicon sentiment: label/score/hits/samples/coverage."""
    s = (text or "").strip()
    if not s:
        return {"label": "neutral", "score": 0, "positive_hits": 0,
                "negative_hits": 0, "tokens_scored": 0,
                "samples": {"positive": [], "negative": []}, "coverage": 0.0}

    tokens = [m.group(0).lower() for m in _WORD_RE.finditer(s)]
    n_tokens = len(tokens) or 1

    pos = 0
    neg = 0
    pos_samples = []
    neg_samples = []

    for i, tok in enumerate(tokens):
        weight = 0
        if tok in _POSITIVE:
            weight = 1
        elif tok in _NEGATIVE:
            weight = -1
        if weight == 0:
            continue
        j0 = max(0, i - lookback)
        if any(tokens[j] in _NEGATORS for j in range(j0, i)):
            weight = -weight
        if weight > 0:
            pos += 1
            if len(pos_samples) < 10:
                pos_samples.append(tok)
        else:
            neg += 1
            if len(neg_samples) < 10:
                neg_samples.append(tok)

    total = pos + neg
    if total == 0:
        label = "neutral"
    else:
        ratio = (pos - neg) / total
        if ratio > 0.2:
            label = "positive"
        elif ratio < -0.2:
            label = "negative"
        else:
            label = "neutral"

    return {
        "label": label,
        "score": pos - neg,
        "positive_hits": pos,
        "negative_hits": neg,
        "tokens_scored": total,
        "samples": {"positive": pos_samples, "negative": neg_samples},
        "coverage": round(total / n_tokens, 4),
    }
