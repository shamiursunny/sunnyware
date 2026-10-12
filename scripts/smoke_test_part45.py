#!/usr/bin/env python3
"""Part 45 smoke test — /openapi.json returns 200 (was 500 before)."""
import ast
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "src" / "sunnyware" / "main.py"
LIVE = "https://shamiur-sunnyware.hf.space"

PASS, FAIL = 0, 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def main():
    print("=" * 62)
    print(" Part 45 — /openapi.json fix")
    print("=" * 62)

    check("main.py present", MAIN.exists())
    if not MAIN.exists():
        return 1
    src = MAIN.read_text(encoding="utf-8")

    print("\n  source:")
    check("_flatten_openapi_routes defined",
          "def _flatten_openapi_routes" in src)
    check("_patched_openapi defined",
          "def _patched_openapi" in src)
    check("app.openapi reassigned",
          "app.openapi = _patched_openapi" in src)
    check("unwraps original_router",
          'getattr(r, "original_router"' in src)
    check("skips response_class=None",
          "if rc is None" in src)

    print("\n  Python syntax:")
    try:
        ast.parse(src)
        check("main.py parses", True)
    except SyntaxError as e:
        check("main.py parses", False, detail=str(e))

    print("\n  local openapi:")
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from sunnyware.main import app
        schema = app.openapi()
        paths = schema.get("paths", {})
        check(f"schema has paths ({len(paths)})", len(paths) > 10)
        check("schema has info.title", "info" in schema and "title" in schema["info"])
        check("/api/agent/run in schema", "/api/agent/run" in paths)
        check("/about in schema", "/about" in paths)
        check("/ui excluded from schema", "/ui" not in paths)
    except Exception as e:
        import traceback
        check("local openapi()", False, detail=str(e))
        traceback.print_exc()

    print("\n  live HF (soft):")
    try:
        req = urllib.request.Request(LIVE + "/openapi.json")
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode("utf-8", errors="replace")
        check(f"/openapi.json HTTP {r.status}", r.status == 200)
        check("/openapi.json contains 'paths'", '"paths"' in body)
    except urllib.error.HTTPError as e:
        print(f"  [SKIP] live /openapi.json HTTP {e.code} (pre-push, expected)")
    except Exception as e:
        print(f"  [SKIP] live check: {type(e).__name__}")

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
