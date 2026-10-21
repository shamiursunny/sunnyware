# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""HF Space entrypoint — launches sunnyware app."""

import os
os.environ["GRADIO_SSR_MODE"] = "false"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"

import sys
import time
from pathlib import Path

try:
    import spaces

    @spaces.GPU
    def _dummy_gpu():
        return "ok"

except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent / "src"))
from sunnyware.main import app  # noqa: E402

demo = app

if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        show_error=True,
        share=False,
        prevent_thread_lock=True,
    )
    print("Server launched in background. Blocking main thread to keep HF Space alive.")
    while True:
        time.sleep(1)
