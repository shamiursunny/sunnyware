# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 145: verified free-tier rate limits per provider.

Researched 2026-10-16 from official documentation:
  groq         : console.groq.com/docs/rate-limits
  gemini       : ai.google.dev/gemini-api/docs/rate-limits
  openrouter   : openrouter.ai/pricing
  pollinations : enter.pollinations.ai + GitHub

IMPORTANT CAVEATS:
  - Groq limits are per ORGANIZATION, not per key.
  - Gemini resets at midnight PACIFIC time, not UTC.
  - OpenRouter free tier is 50 RPD (< $10 lifetime credits);
    1000 RPD after $10 lifetime purchase.
  - Pollinations sk_ secret key has NO rate limit; pk_ keys
    are limited to 1 pollen per IP per hour.
  - Provider-returned Retry-After / retryDelay always wins.
"""

from datetime import datetime, timedelta, timezone


# Verified free-tier limits (2026-10-16)
FREE_TIER_LIMITS = {
    "groq": {
        "rpm": 30,
        "rpd": 1000,
        "tpm": 8000,
        "tpd": 200000,
        "reset_kind": "utc",
        "reset_hour_utc": 0,
        "scope": "organization",
        "notes": "Per-org; multiple keys share the same quota.",
    },
    "gemini": {
        "rpm": 15,
        "rpd": 1500,
        "tpm": 1000000,
        "reset_kind": "pacific",
        "reset_hour_utc": 8,     # 00:00 PT = 08:00 UTC (PST)
        "scope": "project",
        "notes": "Resets at midnight PACIFIC. Varies by model.",
    },
    "openrouter": {
        "rpm": 20,
        "rpd": 50,               # 1000 after $10 lifetime credits
        "rpd_funded": 1000,
        "reset_kind": "utc",
        "reset_hour_utc": 0,
        "scope": "account",
        "notes": "50 RPD until $10 lifetime credits purchased.",
    },
    "pollinations": {
        "rpm": 0,                # unlimited with sk_ key
        "rpd": 0,
        "reset_kind": "none",
        "scope": "key",
        "notes": "sk_ key = no limit; pk_ key = 1 pollen/IP/hour.",
    },
}


def _classify(error: str) -> str:
    """Part 145: guess whether the 429 is daily or per-minute.

    Returns: 'per_day', 'per_minute', or 'unknown'.
    """
    e = (error or "").lower()
    # Daily signals
    for marker in ("per day", "per-day", "perday", "rpd",
                   "tpd", "daily", "1k rpd"):
        if marker in e:
            return "per_day"
    # Minute signals
    for marker in ("per minute", "per-minute", "perminute",
                   "rpm", "tpm", "rolling"):
        if marker in e:
            return "per_minute"
    return "unknown"


def seconds_until_next_reset(provider_name: str) -> float:
    """Return seconds until next daily reset for the given provider.

    Returns 0 if the provider has no daily reset (or unknown).
    Handles UTC and Pacific (auto-DST) reset kinds.
    """
    cfg = FREE_TIER_LIMITS.get((provider_name or "").lower())
    if not cfg:
        return 0.0
    kind = cfg.get("reset_kind")
    if kind == "none":
        return 0.0

    if kind == "utc":
        hour = int(cfg.get("reset_hour_utc", 0) or 0)
        now = datetime.now(timezone.utc)
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return max(0.0, (target - now).total_seconds())

    if kind == "pacific":
        # Midnight America/Los_Angeles — auto-handles DST
        try:
            from zoneinfo import ZoneInfo
            pac = ZoneInfo("America/Los_Angeles")
        except Exception:
            # Fallback: fixed 08:00 UTC
            now = datetime.now(timezone.utc)
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return max(0.0, (target - now).total_seconds())
        now_pac = datetime.now(pac)
        tomorrow = (now_pac + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        return max(0.0, (tomorrow - now_pac).total_seconds())

    return 0.0


def compute_cooldown(provider_name: str, error: str) -> float:
    """Part 145: provider + error-aware cooldown in seconds.

    Priority:
      1. Provider-supplied retry hint (Part 143 _parse_retry_after)
      2. Per-day exhaustion → wait until next daily reset
      3. Per-minute exhaustion → 65s rolling window
      4. Default 60s (was the pre-145 behavior)
    """
    # 1. Honor explicit retry hint
    try:
        from .llm import _parse_retry_after
        hint = _parse_retry_after(error)
        if hint:
            return float(hint) + 5.0
    except Exception:
        pass

    kind = _classify(error)

    if kind == "per_day":
        reset_secs = seconds_until_next_reset(provider_name)
        if reset_secs > 0:
            # +30s safety margin so we don't hit the boundary
            return min(reset_secs + 30.0, 25 * 3600.0)
        # No reset info → fall through
        return 3600.0

    if kind == "per_minute":
        return 65.0

    # 3b. Part 153: pollinations IP cap. Even with an sk_ key,
    #     Pollinations enforces a ~30s per-IP window that fires 402
    #     FREE_LIMIT. Enforce a 35s minimum whenever pollinations
    #     reports a 402.
    if (provider_name or "").lower() == "pollinations":
        if "402" in (error or "") or "free_limit" in (error or "").lower():
            return 35.0

    # 4. Default
    return 60.0


def snapshot() -> dict:
    """For diagnostics / status endpoints."""
    return {
        "providers": dict(FREE_TIER_LIMITS),
        "researched_at": "2026-10-16",
        "sources": {
            "groq": "console.groq.com/docs/rate-limits",
            "gemini": "ai.google.dev/gemini-api/docs/rate-limits",
            "openrouter": "openrouter.ai/pricing",
            "pollinations": "enter.pollinations.ai/keys",
        },
    }
