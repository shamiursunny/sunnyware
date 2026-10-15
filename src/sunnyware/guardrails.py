# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 136: deterministic prompt-injection scanner.

Config:
  SUNNYWARE_INJECTION_GUARD=off|warn|block   (default: off)
  SUNNYWARE_INJECTION_EXTRA_PATTERNS="cat:sev:regex,cat2:sev2:regex2"

Modes:
  off   - scanner does nothing (pre-136 behavior)
  warn  - logs findings, never blocks
  block - rejects when highest_severity == 'high'

Design: pure regex, no LLM, no network. Fast (< 1ms for 10KB input).
Overridable via env var so ops can tune without a redeploy.
"""

import os
import re
from typing import Optional


_SEV_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}
_SEV_NAMES = ("none", "low", "medium", "high")


# (category, severity, name, pattern_string)
_BUILTIN_PATTERNS = (
    # ── instruction_override ────────────────────────────────
    ("instruction_override", "high", "ignore_previous",
     r"\bignore\s+((?:all|the)\s+)?(previous|prior|above|earlier)\s+"
     r"(instructions?|prompts?|rules?|directions?)\b"),
    ("instruction_override", "high", "disregard_previous",
     r"\bdisregard\s+((?:all|the)\s+)?(previous|prior|above|earlier)\s+"
     r"(instructions?|prompts?|rules?|directions?)\b"),
    ("instruction_override", "high", "forget_previous",
     r"\bforget\s+((?:all|the)\s+)?(previous|prior|above|earlier)\s+"
     r"(instructions?|prompts?|rules?|context)\b"),
    ("instruction_override", "high", "new_instructions",
     r"\byour\s+new\s+instructions?\s+(are|is)\b"),
    ("instruction_override", "high", "override_safety",
     r"\b(override|bypass)\s+(your\s+)?(safety|security|filter|guardrail)s?\b"),

    # ── system_prompt_leak ─────────────────────────────────
    ("system_prompt_leak", "high", "print_system",
     r"\b(print|show|reveal|display|output|repeat|echo)\s+(me\s+)?"
     r"(your\s+)?(system\s+)?(prompt|instructions?|rules?|initial\s+message)\b"),
    ("system_prompt_leak", "high", "what_are_your_rules",
     r"\bwhat\s+(are|were)\s+your\s+(system\s+)?"
     r"(prompt|instructions?|rules?|directions?)\b"),
    ("system_prompt_leak", "medium", "verbatim_prompt",
     r"\bverbatim\b.{0,40}\b(prompt|instructions?|rules?)\b"),

    # ── role_play_jailbreak ────────────────────────────────
    ("role_play_jailbreak", "high", "dan_mode",
     r"\b(you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+"
     r"(dan|jailbroken|unrestricted|unfiltered|dev(eloper)?\s+mode)\b"),
    ("role_play_jailbreak", "medium", "no_restrictions",
     r"\b(no\s+(restrictions?|limits?|filters?|rules?)|"
     r"without\s+any\s+(restrictions?|limits?|filters?))\b"),
    ("role_play_jailbreak", "medium", "unrestricted_mode",
     r"\b(unrestricted|unfiltered)\s+(mode|assistant|ai)\b"),

    # ── delimiter_injection ────────────────────────────────
    ("delimiter_injection", "high", "system_tag_close",
     r"</?\s*(system|assistant|user|im_start|im_end)\s*>"),
    ("delimiter_injection", "high", "inst_tag",
     r"\[\s*/?\s*INST\s*\]"),
    ("delimiter_injection", "high", "pipe_special",
     r"<\|(im_start|im_end|endoftext|system|assistant)\|>"),

    # ── exfiltration ───────────────────────────────────────
    ("exfiltration", "medium", "repeat_above",
     r"\brepeat\s+(the\s+)?(text|words?|content|message)\s+"
     r"(above|before|previously|that)\b"),
    ("exfiltration", "medium", "include_above",
     r"\binclude\s+(the\s+)?(text|words?|content|message)\s+"
     r"(above|before|previously|that)\b"),

    # ── encoded_override ───────────────────────────────────
    ("encoded_override", "low", "decode_and_follow",
     r"\b(decode|decrypt|deobfuscate)\b.{0,50}\b(and|then)\b"
     r".{0,30}\b(follow|execute|run|obey)\b"),
    ("encoded_override", "low", "base64_hint",
     r"\bbase64\b.{0,40}\b(follow|execute|decode|obey)\b"),
)


def _compile_patterns(extra: Optional[tuple] = None) -> list:
    out = []
    for cat, sev, name, pat in _BUILTIN_PATTERNS:
        try:
            out.append((cat, sev, name, re.compile(pat, re.IGNORECASE)))
        except re.error:
            continue
    if extra:
        for cat, sev, pat in extra:
            try:
                out.append((cat, sev, "custom", re.compile(pat, re.IGNORECASE)))
            except re.error:
                continue
    return out


def _parse_extra() -> tuple:
    raw = (os.getenv("SUNNYWARE_INJECTION_EXTRA_PATTERNS") or "").strip()
    if not raw:
        return ()
    out = []
    for item in raw.split(","):
        item = item.strip()
        parts = item.split(":", 2)
        if len(parts) != 3:
            continue
        cat, sev, pat = (p.strip() for p in parts)
        if sev not in _SEV_ORDER or not pat:
            continue
        out.append((cat or "custom", sev, pat))
    return tuple(out)


_COMPILED = None


def load_patterns(reload: bool = False) -> list:
    global _COMPILED
    if _COMPILED is None or reload:
        _COMPILED = _compile_patterns(_parse_extra())
    return _COMPILED


def guard_mode() -> str:
    raw = (os.getenv("SUNNYWARE_INJECTION_GUARD") or "off").strip().lower()
    if raw not in ("off", "warn", "block"):
        return "off"
    return raw


def guard_enabled() -> bool:
    return guard_mode() in ("warn", "block")


def scan(text: str, max_bytes: int = 100_000) -> dict:
    """Scan text for injection patterns. Never raises.

    Returns:
        {
            "clean": bool,
            "highest_severity": "none"|"low"|"medium"|"high",
            "findings": [ {category, severity, name, matched, start, end}, ... ],
            "input_length": int,
            "pattern_count": int,
            "truncated": bool,
        }
    """
    if text is None:
        text = ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            text = ""
    input_length = len(text)
    truncated = False
    if input_length > max_bytes:
        text = text[:max_bytes]
        truncated = True

    findings = []
    highest = 0
    patterns = load_patterns()
    for cat, sev, name, regex in patterns:
        try:
            for m in regex.finditer(text):
                start, end = m.start(), m.end()
                findings.append({
                    "category": cat,
                    "severity": sev,
                    "name": name,
                    "matched": text[start:end][:120],
                    "start": start,
                    "end": end,
                })
                if _SEV_ORDER.get(sev, 0) > highest:
                    highest = _SEV_ORDER[sev]
                if len(findings) >= 200:
                    break
        except Exception:
            continue
        if len(findings) >= 200:
            break

    return {
        "clean": len(findings) == 0,
        "highest_severity": _SEV_NAMES[highest],
        "findings": findings,
        "input_length": input_length,
        "pattern_count": len(patterns),
        "truncated": truncated,
    }


def should_block(result: dict) -> bool:
    """Block only in 'block' mode AND highest severity is 'high'."""
    if guard_mode() != "block":
        return False
    return result.get("highest_severity") == "high"


def status() -> dict:
    patterns = load_patterns()
    cats = {}
    for cat, _, _, _ in patterns:
        cats[cat] = cats.get(cat, 0) + 1
    return {
        "guard_mode": guard_mode(),
        "guard_enabled": guard_enabled(),
        "pattern_count": len(patterns),
        "pattern_categories": cats,
        "severities": {s: _SEV_ORDER[s] for s in _SEV_NAMES},
        "block_on": "high",
        "env_var": "SUNNYWARE_INJECTION_GUARD",
        "extra_patterns_env": "SUNNYWARE_INJECTION_EXTRA_PATTERNS",
        "extra_patterns_loaded": len(_parse_extra()),
    }


def reset_cache() -> None:
    global _COMPILED
    _COMPILED = None
