# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Configuration loader — YAML + environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv
import yaml


def _sanitize_db_url(url: str) -> str:
    """Strip common wrappers from DB URL."""
    if not url:
        return url
    url = url.strip().strip("'\"")
    if url.lower().startswith("psql "):
        url = url[5:].strip().strip("'\"")
    return url


class Config:
    def __init__(self, raw: dict):
        raw = raw or {}
        self.raw = raw
        self.generic_agent_path = raw.get("generic_agent_path", "/app/GenericAgent")
        self.max_context_tokens = int(raw.get("max_context_tokens", 1048576))

        # Database
        self.neon_database_url = _sanitize_db_url(os.getenv("NEON_DATABASE_URL", ""))

        # LLM (env overrides YAML)
        self.llm_base_url = os.getenv(
            "LLM_BASE_URL", raw.get("llm_base_url", "http://localhost:11434/v1")
        )
        self.llm_api_key = os.getenv("LLM_API_KEY", raw.get("llm_api_key", "ollama"))
        self.llm_model = os.getenv(
            "LLM_MODEL", raw.get("llm_model", "gemma2-2b-tuned-stable:latest")
        )


def load_config() -> Config:
    load_dotenv()
    path = Path("./config/sunnyware.yaml")
    raw = yaml.safe_load(path.read_text()) if path.exists() else {}
    return Config(raw)
