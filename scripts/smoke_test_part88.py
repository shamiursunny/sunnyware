"""Part 88 smoke test -- SSE 'final' error is surfaced in the WebUI."""
from pathlib import Path
import sys

WEBUI = Path(__file__).resolve().parent.parent / "src" / "sunnyware" / "webui.py"

CHECKS = [
    ("streamError declared",              "let streamError = ''"),
    ("final handler reads ok:false",      "data.ok === false && data.error"),
    ("final handler assigns streamError", "streamError = String(data.error)"),
    ("end-of-stream uses streamError",    "if (streamError)"),
    ("old fallback still present",        "addMsg('(empty response)', 'error')"),
]

def main() -> int:
    if not WEBUI.exists():
        print(f"FAIL  webui.py not found at {WEBUI}")
        return 1
    src = WEBUI.read_text(encoding="utf-8")
    passed = failed = 0
    for name, needle in CHECKS:
        if needle in src:
            print(f"PASS  {name}")
            passed += 1
        else:
            print(f"FAIL  {name}  (missing: {needle!r})")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
