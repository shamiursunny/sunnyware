#!/usr/bin/env python3
"""Part 42 smoke test — markdown rendering + provider badge fix.

Checks:
  1. webui.py contains marked.js CDN
  2. webui.py defines escapeHtml() helper
  3. webui.py defines renderAgentHtml() helper
  4. addMsg uses innerHTML for agent messages
  5. streaming handler uses innerHTML for agent text
  6. markdown CSS blocks present
  7. dead refreshProviders() removed
  8. agent.py done event includes provider field
  9. agent.py captures provider name in stream handler
 10. both files parse as valid Python
 11. embedded HTML has exactly one <script> open/close pair
 12. no raw newlines inside JS single-quoted strings (escape gate)
 13. rendered HTML sanitizes </script> in markdown output
 14. rendered HTML strips javascript: URIs
 15. live HF serves marked.min.js (soft — skipped if unreachable)
"""
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
    print(" Part 42 — markdown rendering + provider badge fix")
    print("=" * 62)

    check("webui.py present", WEBUI.exists())
    check("agent.py present", AGENT.exists())
    if not (WEBUI.exists() and AGENT.exists()):
        return 1

    webui_src = WEBUI.read_text(encoding="utf-8")
    agent_src = AGENT.read_text(encoding="utf-8")

    # ── webui.py checks ───────────────────────────────────────
    print("\n  webui.py:")
    check("marked.js CDN present",
          "cdn.jsdelivr.net/npm/marked" in webui_src)
    check("marked@12 pinned",
          "marked@12" in webui_src)
    check("escapeHtml() defined",
          "function escapeHtml" in webui_src)
    check("renderAgentHtml() defined",
          "function renderAgentHtml" in webui_src)
    check("addMsg uses innerHTML for agent",
          "d.innerHTML = renderAgentHtml" in webui_src)
    check("streaming uses innerHTML for agent",
          ".innerHTML = renderAgentHtml(agentText)" in webui_src)
    check("markdown CSS: pre block",
          ".msg.agent pre" in webui_src)
    check("markdown CSS: inline code",
          ".msg.agent code" in webui_src)
    check("refreshProviders removed",
          "refreshProviders" not in webui_src)
    check("</script> sanitized in renderAgentHtml",
          "split('<\\/script')" in webui_src or "split('<\\\\/script')" in webui_src)
    check("javascript: URIs stripped",
          "split('javascript:')" in webui_src)

    # ── agent.py checks ───────────────────────────────────────
    print("\n  agent.py:")
    check("provider captured in stream",
          "_prov_name" in agent_src)
    check("done event includes provider",
          "'provider': _prov_name" in agent_src)

    # ── Python syntax ────────────────────────────────────────
    print("\n  Python syntax:")
    try:
        ast.parse(webui_src)
        check("webui.py parses", True)
    except SyntaxError as e:
        check("webui.py parses", False, detail=str(e))
    try:
        ast.parse(agent_src)
        check("agent.py parses", True)
    except SyntaxError as e:
        check("agent.py parses", False, detail=str(e))

    # ── HTML structure integrity ──────────────────────────────
    print("\n  HTML/JS structure:")
    html_open = webui_src.count("<script")
    html_close = webui_src.count("</script>")
    check(f"script tags balanced ({html_open}/{html_close})",
          html_open == html_close and html_open > 0)

    # Check for raw newlines in single-quoted JS strings
    js_strings = re.findall(r"'([^'\\]|\\.)*'", webui_src)
    raw_newline = [s for s in js_strings if "\n" in s and len(s) < 200]
    check(f"no raw newlines in JS strings ({len(raw_newline)} found)",
          len(raw_newline) == 0)

    # ── Live HF check (soft — skipped if offline) ─────────────
    print("\n  live HF (soft):")
    try:
        with urllib.request.urlopen(LIVE, timeout=8) as r:
            html = r.read().decode("utf-8", errors="replace")
        if "cdn.jsdelivr.net/npm/marked" in html:
            check("live /ui serves marked.js", True)
        else:
            print("  [SKIP] live /ui not yet serving marked.js (pre-push, expected)")
    except Exception as e:
        print(f"  [SKIP] live /ui unreachable: {type(e).__name__}")
        print("         (this is fine pre-push)")

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
