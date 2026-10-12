#!/usr/bin/env python3
"""Extract the served JS from webui.py and run `node --check` on it.

Catches:
  - Regex literals with unbalanced escapes (the Part 43 bug)
  - Unclosed strings / braces / parentheses
  - Any JS that a browser would reject wholesale
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBUI = ROOT / "src" / "sunnyware" / "webui.py"


def main():
    src = WEBUI.read_text(encoding="utf-8")
    # Grab the last <script>...</script> block (the app JS)
    matches = list(re.finditer(r"<script>(.*?)</script>", src, re.DOTALL))
    if not matches:
        print("[FAIL] no <script> block found in webui.py")
        return 1
    js = matches[-1].group(1)
    print(f"[info] extracted {len(js)} chars of JS")

    result = subprocess.run(
        ["node", "--check", "-"],
        input=js, text=True, capture_output=True, timeout=15,
    )
    if result.returncode == 0:
        print("[PASS] node --check: JS parses cleanly")
        return 0
    print("[FAIL] node --check reported:")
    print(result.stderr[:600])
    return 1


if __name__ == "__main__":
    sys.exit(main())
