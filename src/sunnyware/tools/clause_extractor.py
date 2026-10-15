# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 128: contract clause extractor.

Hebbia ISD-inspired but fully deterministic. Given contract/legal
text, extract structured clauses by keyword matching — no LLM, no
network, no external calls.
"""
import re

_SENT_RE = re.compile(r"(?<=[.!?])\s+")

_CLAUSE_TYPES = {
    "termination": [
        "terminate", "terminates", "terminated", "termination",
        "terminations", "cancel", "cancellation", "cancellations",
        "expire", "expiration", "notice period", "notice",
    ],
    "indemnification": [
        "indemnify", "indemnification", "indemnity", "hold harmless",
        "defend against",
    ],
    "liability": [
        "liability", "liable", "damages", "consequential damages",
        "limitation of liability",
    ],
    "confidentiality": [
        "confidential", "confidentiality", "non-disclosure",
        "proprietary information", "trade secret",
    ],
    "payment_terms": [
        "payment", "invoice", "invoiced", "due date",
        "net 30", "net 60", "net 90", "remit", "remittance",
    ],
    "governing_law": [
        "governing law", "governed by", "jurisdiction", "venue",
        "choice of law", "courts of",
    ],
    "warranties": [
        "warrant", "warrants", "warranted", "warranty", "warranties",
        "represent", "represents", "represented", "representation",
        "covenant", "covenants",
    ],
    "force_majeure": [
        "force majeure", "act of god", "beyond reasonable control",
        "acts of war", "natural disaster",
    ],
    "assignment": [
        "assign", "assignment", "transfer", "delegate",
        "successors and assigns",
    ],
    "limits": [
        "limit", "limitation", "maximum", "cap", "aggregate",
        "deductible", "retention", "ceiling",
    ],
    "coverage": [
        "coverage", "covered", "insured", "policy", "premium",
        "policyholder", "policy term",
    ],
    "exclusions": [
        "exclude", "excluded", "exclusion", "does not cover",
        "shall not apply", "not covered",
    ],
    "renewal": [
        "renew", "renewal", "auto-renew", "automatic renewal",
        "extension term",
    ],
    "notice": [
        "written notice", "notice", "notify", "notification",
        "notification period", "in writing",
    ],
}


def list_clause_types():
    return sorted(_CLAUSE_TYPES.keys())


def _score_sentence(sentence, patterns):
    s = sentence.lower()
    score = 0
    hits = []
    for p in patterns:
        if " " in p or "-" in p:
            c = s.count(p)
            if c:
                score += c
                hits.append(p)
        else:
            m = re.findall(r"\b" + re.escape(p) + r"\b", s)
            if m:
                score += len(m)
                hits.append(p)
    return score, hits


def _split_sentences(text):
    if not text:
        return []
    t = re.sub(r"[ \t]+", " ", text).strip()
    parts = _SENT_RE.split(t)
    return [s.strip() for s in parts if len(s.strip()) >= 20]


def extract_clauses(text, clause_types=None, min_score=1):
    if not isinstance(text, str) or not text.strip():
        return {"error": "text is required"}

    if clause_types is None:
        types = list(_CLAUSE_TYPES.keys())
    elif isinstance(clause_types, str):
        types = [t.strip().lower() for t in clause_types.split(",")
                 if t.strip()]
    else:
        types = [str(t).strip().lower() for t in clause_types
                 if str(t).strip()]

    unknown = [t for t in types if t not in _CLAUSE_TYPES]
    if unknown:
        return {"error": "unknown clause type(s): " + ", ".join(unknown),
                "available": list_clause_types()}

    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return {"error": "text too short (need >= 2 sentences)",
                "sentences_found": len(sentences),
                "clauses": []}

    clauses = []
    pos = 0
    for sent in sentences:
        idx = text.find(sent, pos)
        if idx < 0:
            idx = pos
        sent_start = idx
        sent_end = idx + len(sent)
        pos = sent_end

        best_type = None
        best_score = 0
        best_hits = []
        for t in types:
            sc, hits = _score_sentence(sent, _CLAUSE_TYPES[t])
            if sc > best_score:
                best_score = sc
                best_type = t
                best_hits = hits

        if best_type is None or best_score < min_score:
            continue

        if (clauses
                and clauses[-1]["type"] == best_type
                and clauses[-1]["_last_end"] >= sent_start - 5):
            clauses[-1]["text"] += " " + sent
            clauses[-1]["char_end"] = sent_end
            clauses[-1]["score"] += best_score
            for h in best_hits:
                if h not in clauses[-1]["keywords_matched"]:
                    clauses[-1]["keywords_matched"].append(h)
            clauses[-1]["_last_end"] = sent_end
        else:
            clauses.append({
                "type": best_type,
                "score": best_score,
                "keywords_matched": list(best_hits),
                "text": sent,
                "char_start": sent_start,
                "char_end": sent_end,
                "_last_end": sent_end,
            })

    for c in clauses:
        c.pop("_last_end", None)

    by_type = {}
    for c in clauses:
        by_type[c["type"]] = by_type.get(c["type"], 0) + 1

    return {
        "input_length": len(text),
        "sentence_count": len(sentences),
        "clause_count": len(clauses),
        "types_searched": types,
        "by_type": by_type,
        "clauses": clauses,
    }


class ClauseExtractorTool:
    name = "clause_extractor"
    description = (
        "Extract structured clauses from contract / policy text. "
        "Deterministic keyword matching — no LLM, no network. "
        "Clause types: termination, indemnification, liability, "
        "confidentiality, payment_terms, governing_law, warranties, "
        "force_majeure, assignment, limits, coverage, exclusions, "
        "renewal, notice. Returns per-clause {type, score, keywords, "
        "text, char_start, char_end} with adjacent same-type sentences "
        "merged. Use on policy PDFs (after extracting text), MSA/NDA "
        "contracts, and terms of service."
    )
    parameters = {
        "text": {
            "type": "string",
            "description": "Raw contract / policy text",
            "required": True,
        },
        "clause_types": {
            "type": "string",
            "description": "Comma-separated filter (default: all). E.g. 'coverage,exclusions,limits'",
            "required": False,
        },
        "min_score": {
            "type": "integer",
            "description": "Minimum keyword score to keep a sentence (default 1)",
            "required": False,
        },
        "action": {
            "type": "string",
            "description": "Optional: 'list_types' to enumerate available types",
            "required": False,
        },
    }

    async def run(self, args: dict) -> dict:
        action = (args.get("action") or "").strip().lower()
        if action == "list_types":
            return {"types": list_clause_types()}

        text = args.get("text")
        if not isinstance(text, str) or not text.strip():
            return {"error": "text is required (raw contract text)"}

        try:
            ms = int(args.get("min_score") or 1)
        except Exception:
            ms = 1
        ms = max(1, ms)

        try:
            return extract_clauses(
                text,
                clause_types=args.get("clause_types"),
                min_score=ms,
            )
        except Exception as e:
            return {"error": type(e).__name__ + ": " + str(e)}
