# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""HF Space entrypoint — launches sunnyware app.

Thin wrapper — HF Gradio Spaces look for app.py at repo root.
All logic lives in src/sunnyware/main.py.
"""

import os
import sys
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sunnyware.main import app   # noqa: E402

# HF Spaces auto-detects `demo` or `app` and launches. We expose both.
demo = app

if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        show_error=True,
    )
