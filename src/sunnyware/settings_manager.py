import json
import os
from pathlib import Path
from . import paths

SETTINGS_FILE = paths.data_root() / "settings.json"

def get_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    apply_settings()

def apply_settings():
    """Load keys from settings.json into os.environ so all LLM providers pick them up."""
    data = get_settings()
    for key, value in data.items():
        if value and isinstance(value, str):
            os.environ[key] = value
