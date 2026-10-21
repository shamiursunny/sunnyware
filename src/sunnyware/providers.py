# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Multi-provider registry for the LLM router (Part 32).

Providers are declared in env var LLM_PROVIDERS as a comma-separated
priority list. Per-provider config comes from <NAME>_BASE_URL,
<NAME>_API_KEY, <NAME>_MODEL.

Example .env:
    LLM_PROVIDERS=groq,gemini,openrouter,local
    GROQ_BASE_URL=https://api.groq.com/openai/v1
    GROQ_API_KEY=gsk_...
    GROQ_MODEL=openai/gpt-oss-20b
    GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
    GEMINI_API_KEY=AIza_...
    GEMINI_MODEL=gemini-2.0-flash
    OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
    OPENROUTER_API_KEY=sk-or-...
    OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free
    LOCAL_BASE_URL=http://localhost:8080/v1
    LOCAL_API_KEY=local
    LOCAL_MODEL=minicpm5-2b

If LLM_PROVIDERS is unset, we fall back to the legacy single-provider
config (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL).
"""

import os
import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str
    max_prompt_tokens: int = 0   # Part 99: 0 = no limit
    provider_type: str = "http"  # "http" or "local"
    supports_tools: bool = True   # Part 152: OpenAI-style tools
    cooldown_until: float = 0.0
    last_error: str = ""
    success_count: int = 0
    fail_count: int = 0
    last_success_ts: float = 0.0

    def is_cooling(self) -> bool:
        return time.time() < self.cooldown_until

    def cooldown_remaining(self) -> float:
        return max(0.0, self.cooldown_until - time.time())

    def mark_cooldown(self, seconds: float) -> None:
        self.cooldown_until = time.time() + seconds

    def record_success(self) -> None:
        self.success_count += 1
        self.last_success_ts = time.time()
        self.last_error = ""

    def record_failure(self, err: str) -> None:
        self.fail_count += 1
        self.last_error = (err or "")[:200]

    def status(self) -> dict:
        return {
            "name": self.name,
            "type": self.provider_type,
            "supports_tools": self.supports_tools,
            "model": self.model,
            "max_prompt_tokens": self.max_prompt_tokens,
            "base_url": self.base_url.split("/")[2] if "://" in self.base_url else self.base_url,
            "cooling": self.is_cooling(),
            "cooldown_remaining_s": round(self.cooldown_remaining(), 1),
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "last_error": self.last_error,
        }


_PROVIDERS: Optional[List[Provider]] = None


def load_providers(reload: bool = False) -> List[Provider]:
    """Load providers from env. Cached after first call."""
    global _PROVIDERS
    if _PROVIDERS is not None and not reload:
        return _PROVIDERS

    priority = (os.getenv("LLM_PROVIDERS") or "").strip()

    if not priority:
        # Legacy single-provider mode
        _PROVIDERS = [Provider(
            name="default",
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("LLM_API_KEY", "ollama"),
            model=os.getenv("LLM_MODEL", "gemma2-2b-tuned-stable:latest"),
        )]
        return _PROVIDERS

    # Part 99: per-provider default max prompt tokens (0 = no limit).
    # These are conservative defaults based on each provider's documented
    # or observed input limits. Override with {PREFIX}_MAX_PROMPT_TOKENS.
    _default_max_pt = {
        "groq": 128000,          # Llama 3.3 70B supports 128k context
        "gemini": 1000000,     # 1M context
        "openrouter": 32000,   # varies by model; safe default
        "pollinations": 32000,
        "mistral": 32000,
        "nvidia": 8000,
        "local": 0,            # in-process, no HTTP limits
    }

    out: List[Provider] = []
    for name in [n.strip().lower() for n in priority.split(",") if n.strip()]:
        prefix = name.upper()
        base_url = (os.getenv(f"{prefix}_BASE_URL") or "").strip()
        api_key = (os.getenv(f"{prefix}_API_KEY") or "").strip()
        model = (os.getenv(f"{prefix}_MODEL") or "").strip()
        if not (base_url and model):
            # Skip misconfigured providers (missing URL or model)
            continue
        ptype = "local" if name == "local" else "http"
        # Part 99: max prompt tokens — env override, else default
        max_pt = _default_max_pt.get(name, 0)
        env_pt = (os.getenv(f"{prefix}_MAX_PROMPT_TOKENS") or "").strip()
        if env_pt and name != "groq":  # Part 272: Ignore stale limit for Groq
            try:
                max_pt = int(env_pt)
            except ValueError:
                pass
        else:
            # Part 100: learned limit beats hardcoded default.
            # Env override always wins (skipped above).
            try:
                from . import provider_limits as _pl
                learned = _pl.get_learned(name)
                if learned is not None and (not max_pt or learned < max_pt):
                    max_pt = learned
            except Exception:
                pass
        # Part 152: Pollinations free tier rejects requests with
        # OpenAI-style tool schemas. Treat as tools-unsupported.
        supports_tools = True
        out.append(Provider(
            name=name,
            base_url=base_url.rstrip("/"),
            api_key=api_key or "local",
            model=model,
            max_prompt_tokens=max_pt,
            provider_type=ptype,
            supports_tools=supports_tools,
        ))

    _PROVIDERS = out
    return _PROVIDERS


def provider_statuses() -> List[dict]:
    """Snapshot for /api/providers/status and health checks."""
    try:
        return [p.status() for p in load_providers()]
    except Exception:
        return []


def reset_for_tests() -> None:
    """Test helper - clears the cached provider list."""
    global _PROVIDERS
    _PROVIDERS = None
