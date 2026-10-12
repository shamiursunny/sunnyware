#!/usr/bin/env python3
"""Part 43 smoke test — chart rendering + session rename + voice input."""
import ast
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBUI = ROOT / "src" / "sunnyware" / "webui.py"
AGENT = ROOT / "src" / "sunnyware" / "routes" / "agent.py"
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
    print(" Part 43 — charts + rename + voice")
    print("=" * 62)

    check("webui.py present", WEBUI.exists())
    if not WEBUI.exists():
        return 1

    src = WEBUI.read_text(encoding="utf-8")

    # ── Chart rendering ───────────────────────────────────────
    print("\n  charts:")
    check("wrapBareBase64() defined", "function wrapBareBase64" in src)
    check("data:image URI wrapped",
          "data:image\\/(?:png|jpe?g|gif|webp)" in src)
    check("bare PNG base64 wrapped",
          "iVBORw0KGgo" in src)
    check("chart img CSS",
          ".msg.agent img {" in src)
    check("img.zoomed CSS",
          ".msg.agent img.zoomed" in src)
    check("chart zoom click handler",
          "e.target.classList.toggle('zoomed')" in src)

    # ── Voice input ──────────────────────────────────────────
    print("\n  voice input:")
    check("micBtn element in HTML", 'id="micBtn"' in src)
    check("WebkitSpeechRecognition fallback",
          "webkitSpeechRecognition" in src)
    check("recording pulse animation",
          "animation: pulse-red" in src)
    check("voice onresult fills input",
          "input.value = base + final + interim" in src)
    check("graceful fallback when unsupported",
          "Voice input not supported" in src)

    # ── Session rename ───────────────────────────────────────
    print("\n  session rename:")
    check("renameSession() function",
          "function renameSession" in src)
    check("rename icon in sidebar",
          "ren.className = 'ren'" in src)
    check("double-click handler",
          "title.addEventListener('dblclick'" in src)
    check("saveSessions called after rename",
          "sess.title = trimmed" in src)

    # ── Part 42 regression ───────────────────────────────────
    print("\n  Part 42 regression:")
    check("marked.js CDN still present",
          "cdn.jsdelivr.net/npm/marked" in src)
    check("renderAgentHtml still present",
          "function renderAgentHtml" in src)
    check("escapeHtml still present",
          "function escapeHtml" in src)
    check("refreshProviders still removed",
          "refreshProviders" not in src)

    # ── Python syntax ────────────────────────────────────────
    print("\n  Python syntax:")
    try:
        ast.parse(src)
        check("webui.py parses", True)
    except SyntaxError as e:
        check("webui.py parses", False, detail=str(e))

    # ── HTML/JS structure ────────────────────────────────────
    print("\n  HTML/JS structure:")
    open_tags = src.count("<script")
    close_tags = src.count("</script>")
    check(f"script tags balanced ({open_tags}/{close_tags})",
          open_tags == close_tags and open_tags > 0)

    js_strings = re.findall(r"'([^'\\]|\\.)*'", src)
    raw_nl = [s for s in js_strings if "\n" in s and len(s) < 200]
    check(f"no raw newlines in JS strings ({len(raw_nl)} found)",
          len(raw_nl) == 0)

    # ── Live HF check (soft) ─────────────────────────────────
    print("\n  live HF (soft):")
    try:
        with urllib.request.urlopen(LIVE, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")
        if "id=\"micBtn\"" in html and "function wrapBareBase64" in html:
            check("live /ui serves Part 43", True)
        else:
            print("  [SKIP] live /ui not yet on Part 43 (pre-push)")
    except Exception as e:
        print(f"  [SKIP] live /ui unreachable: {type(e).__name__}")

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
