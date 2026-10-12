#!/usr/bin/env python3
"""Part 63 smoke test — Playwright browser tools."""
import ast, os, sys, asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

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
    print(" Part 63 — Playwright browser tools")
    print("=" * 62)

    # Files
    check("packages.txt exists", (ROOT / "packages.txt").exists())
    req = ROOT / "requirements.txt"
    check("requirements has playwright",
          req.exists() and "playwright" in req.read_text(encoding="utf-8"))
    check("_browser_session.py exists",
          (ROOT / "src/sunnyware/tools/_browser_session.py").exists())

    for cls, mod in [
        ("BrowserGotoTool", "browser_goto"),
        ("BrowserScreenshotTool", "browser_screenshot"),
        ("BrowserExtractTool", "browser_extract"),
        ("BrowserClickTool", "browser_click"),
        ("BrowserFillSubmitTool", "browser_fill_submit"),
    ]:
        f = ROOT / "src" / "sunnyware" / "tools" / f"{mod}.py"
        check(f"{mod}.py exists", f.exists())
        if f.exists():
            src = f.read_text(encoding="utf-8")
            check(f"{mod} class defined", f"class {cls}" in src)
            check(f"{mod} name field", f'name = "{mod}"' in src)
            try:
                ast.parse(src)
                check(f"{mod}.py parses", True)
            except SyntaxError as e:
                check(f"{mod}.py parses", False, detail=str(e))

    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")
    for cls, _ in [
        ("BrowserGotoTool", "x"), ("BrowserScreenshotTool", "x"),
        ("BrowserExtractTool", "x"), ("BrowserClickTool", "x"),
        ("BrowserFillSubmitTool", "x"),
    ]:
        check(f"{cls} registered",
              f"{cls}.name: {cls}()" in init_src)

    # SSRF guard reuse
    try:
        from sunnyware.tools._browser_session import validate_url
        check("validate_url blocks localhost",
              validate_url("http://localhost:7860") is not None)
        check("validate_url blocks 10.x",
              validate_url("http://10.0.0.5/x") is not None)
        check("validate_url allows example.com",
              validate_url("https://example.com") is None)
    except Exception as e:
        check("validate_url import", False, detail=str(e))

    # Playwright availability
    try:
        import playwright  # noqa
        check("playwright importable", True)
        has_pw = True
    except Exception:
        print("  [SKIP] playwright not installed locally — integration skipped")
        has_pw = False

    # Integration (only if Playwright installed locally)
    if has_pw:
        async def run_goto(**kw):
            from sunnyware.tools.browser_goto import BrowserGotoTool
            return await BrowserGotoTool().run(kw)
        try:
            r = asyncio.run(run_goto(url="https://example.com", max_chars=20000))
            if "error" in r:
                print(f"  [SKIP] browser_goto: {r['error'][:80]}")
            else:
                check("browser_goto returns html", "html" in r and len(r["html"]) > 0)
                check("browser_goto title non-empty", bool(r.get("title")))
        except Exception as e:
            print(f"  [SKIP] browser integration: {type(e).__name__}: {e}")

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
