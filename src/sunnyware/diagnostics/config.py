"""Configuration flags for diagnostics."""
import os

DIAGNOSTICS_ENABLED = os.getenv("DIAGNOSTICS_ENABLED", "1").lower() in ("1", "true", "yes")
DIAGNOSTICS_STRICT = os.getenv("DIAGNOSTICS_STRICT", "0").lower() in ("1", "true", "yes")
