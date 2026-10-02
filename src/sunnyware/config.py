# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Configuration loader — YAML + environment variables."""

import os
import re
from pathlib import Path
from dotenv import load_dotenv
import yaml


def _sanitize_db_url(url: str) -> str:
    """Strip common wrappers from DB URL.

    Handles copy-paste from Neon dashboard which may include:
      - psql 'postgresql://...'  (with psql prefix + quotes)
      - "postgresql://..."       (double quotes)
      - trailing newlines/spaces
    """
    if not url:
        return url
    url = url.strip().strip("'\"")
    # Remove 'psql ' prefix if present
    if url.lower().startswith("psql "):
        url = url[5:].strip().strip("'\"")
    return url


class Config:
    def __init__(self, raw: dict):
        raw = raw or {}
        self.raw = raw
        self.generic_agent_path = raw.get("generic_agent_path", "/app/GenericAgent")
        self.llm_base_url = raw.get("llm_base_url", "http://localhost:4000/v1")
        self.llm_api_key = raw.get("llm_api_key", "sk-sunnyware-local")
        self.max_context_tokens = int(raw.get("max_context_tokens", 1048576))
        # Neon (from environment) — sanitize wrappers
        self.neon_database_url = _sanitize_db_url(os.getenv("NEON_DATABASE_URL", ""))


def load_config() -> Config:
    load_dotenv()
    path = Path("./config/sunnyware.yaml")
    raw = yaml.safe_load(path.read_text()) if path.exists() else {}
    return Config(raw)
