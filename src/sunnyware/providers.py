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
            "model": self.model,
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

    out: List[Provider] = []
    for name in [n.strip().lower() for n in priority.split(",") if n.strip()]:
        prefix = name.upper()
        base_url = (os.getenv(f"{prefix}_BASE_URL") or "").strip()
        api_key = (os.getenv(f"{prefix}_API_KEY") or "").strip()
        model = (os.getenv(f"{prefix}_MODEL") or "").strip()
        if not (base_url and model):
            # Skip misconfigured providers (missing URL or model)
            continue
        out.append(Provider(
            name=name,
            base_url=base_url.rstrip("/"),
            api_key=api_key or "local",
            model=model,
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
