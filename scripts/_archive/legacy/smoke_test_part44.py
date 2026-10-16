#!/usr/bin/env python3
"""Part 44 smoke test — responsive CSS + mic permission UX + TV mode."""
import ast
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBUI = ROOT / "src" / "sunnyware" / "webui.py"
LIVE = "https://shamiur-sunnyware.hf.space/ui"

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
    print(" Part 44 — responsive + mic permission + TV mode")
    print("=" * 62)

    check("webui.py present", WEBUI.exists())
    if not WEBUI.exists():
        return 1
    src = WEBUI.read_text(encoding="utf-8")

    print("\n  responsive:")
    check("mobile menu button", 'id="mobileMenuBtn"' in src)
    check("overlay backdrop", 'id="overlayBackdrop"' in src)
    check("mobile drawer (translateX)", "translateX(-100%)" in src)
    check("tablet breakpoint 641-900",
          "min-width: 641px" in src and "max-width: 900px" in src)
    check("large screen 1600px+", "min-width: 1600px" in src)
    check("touch target media query", "@media (pointer: coarse)" in src)
    check("body.mobile-menu-open class", "body.mobile-menu-open" in src)

    print("\n  mic permission:")
    check("getUserMedia preflight", "navigator.mediaDevices.getUserMedia" in src)
    check("permissions.query for mic state",
          "navigator.permissions.query" in src)
    check("auto-language", "navigator.language" in src)
    check("mic-denied CSS class", ".mic-denied" in src)
    check("NotAllowedError handled", "NotAllowedError" in src)
    check("NotFoundError handled", "NotFoundError" in src)

    print("\n  tv mode:")
    check("TV UA detection", "detectTVMode" in src)
    check("SmartTV/Tizen sign list",
          "'Tizen'" in src and "'Web0S'" in src)
    check("body.tv-mode CSS", "body.tv-mode" in src)
    check("TV focus outlines", "outline: 3px solid" in src)

    print("\n  mobile menu wiring:")
    check("initMobileMenu present", "initMobileMenu" in src)
    check("ESC closes menu", "e.key === 'Escape'" in src)
    check("auto-close on session click", "closest('.sess')" in src)

    print("\n  Part 43 regression:")
    check("wrapBareBase64 still present", "wrapBareBase64" in src)
    check("renameSession still present", "function renameSession" in src)
    check("marked CDN still present", "cdn.jsdelivr.net/npm/marked" in src)

    print("\n  Python syntax:")
    try:
        ast.parse(src)
        check("webui.py parses", True)
    except SyntaxError as e:
        check("webui.py parses", False, detail=str(e))

    print("\n  HTML/JS structure:")
    check("script tags balanced",
          src.count("<script") == src.count("</script>"))

    print("\n  live HF (soft):")
    try:
        with urllib.request.urlopen(LIVE, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")
        if "mobileMenuBtn" in html and "detectTVMode" in html:
            check("live /ui serves Part 44", True)
        else:
            print("  [SKIP] live /ui not yet on Part 44 (pre-push)")
    except Exception as e:
        print(f"  [SKIP] live /ui unreachable: {type(e).__name__}")

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
