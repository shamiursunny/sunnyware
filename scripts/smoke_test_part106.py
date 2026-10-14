# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 106 smoke test - persistent image attachments."""
from pathlib import Path
import ast, sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

print("=== Part 106: persistent image attachments ===")

# 1. attachments.py
am = SRC / "attachments.py"
check("src/sunnyware/attachments.py exists", am.is_file())
att = am.read_text(encoding="utf-8") if am.is_file() else ""
try:
    ast.parse(att)
    check("attachments.py parses", True)
except SyntaxError as e:
    check("attachments.py parses", False, str(e))
for fn in ["def save_base64(", "def resolve_path(", "def stats(",
           "def path_source(", "def root("]:
    check(f"{fn}", fn in att)
check("POSIX-only /data detection", 'os.name == "posix"' in att)
check("traversal guard (rejects '/')", '"/",' in att or "'/'" in att)
check("ext whitelist", "_EXT_WHITELIST" in att)

# 2. Serving route in meta.py
meta = (SRC / "routes" / "meta.py").read_text(encoding="utf-8")
check("/api/attachments/{att_id}.{ext} route",
      '@router.get("/api/attachments/{att_id}.{ext}")' in meta)
check("/api/attachments/stats route",
      '@router.get("/api/attachments/stats")' in meta)
check("FileResponse imported",
      "FileResponse" in meta)
check("Cache-Control immutable on serving",
      "public, max-age=31536000, immutable" in meta)

# 3. Tools save attachments
img = (SRC / "tools" / "image_generate.py").read_text(encoding="utf-8")
check("image_generate saves attachment",
      "attachment_url" in img and "attachments as _att" in img)
chart = (SRC / "tools" / "chart_from_data.py").read_text(encoding="utf-8")
check("chart_from_data saves attachment",
      "attachment_url" in chart and "attachments as _att" in chart)

# 4. Orchestrator collects
orc = (SRC / "orchestrator.py").read_text(encoding="utf-8")
check("orchestrator _attachments init", "_attachments = []" in orc)
check("orchestrator native path collects",
      orc.count("_attachments.append") >= 2)
check("orchestrator returns attachments",
      orc.count('"attachments": _attachments') >= 1)

# 5. routes/agent.py
ag = (SRC / "routes" / "agent.py").read_text(encoding="utf-8")
check("_strip_broken_b64_md helper",
      "def _strip_broken_b64_md(" in ag)
check("strip applied to non-stream",
      ag.count("_strip_broken_b64_md(") >= 3)
check("log_event payload has attachments",
      ag.count('"attachments": agent_result.get("attachments")') >= 1)
check("final SSE has attachments",
      ag.count('"attachments": result.get("attachments")') >= 2)

# 6. WebUI renders from history
wui = (SRC / "webui.py").read_text(encoding="utf-8")
check("fetchHistoryFromNeon strips broken md",
      "_clean = content.replace" in wui)
check("fetchHistoryFromNeon carries attachments",
      "attachments: _atts" in wui)
check("loadSession renders attachments",
      "render stored attachments below the bubble" in wui)
check("loadSession uses msg-image class",
      "_img.className = 'msg-image'" in wui)
check("final handler captures attachments",
      "lastAttachments = data.attachments" in wui)
check("lastAttachments declared",
      "let lastAttachments = []" in wui)
check("persist attachments after stream",
      "persist attachments on the last stored agent message" in wui)
check("persist uses saveSessions",
      "saveSessions(_ss)" in wui)

# 7. File parses
try:
    ast.parse(wui)
    check("webui.py parses", True)
except SyntaxError as e:
    check("webui.py parses", False, str(e))

# 8. Live import sanity
sys.path.insert(0, str(SRC.parent))
try:
    from sunnyware import attachments as _a
    check("attachments module imports", True)
    st = _a.stats()
    check("attachments.stats() returns dict", isinstance(st, dict))
    check("stats has 'file_count'", "file_count" in st)
    check("stats has 'path_source'", "path_source" in st)
    # Round-trip test with a tiny PNG
    import base64 as _b64
    tiny_png = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlE"
                "QVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    saved = _a.save_base64(tiny_png, "png")
    check("save_base64 returns id+url", bool(saved and saved.get("id") and saved.get("url")))
    if saved:
        p = _a.resolve_path(saved["id"], saved["ext"])
        check("resolve_path finds it", p is not None and p.is_file())
        # Cleanup
        try: p.unlink()
        except Exception: pass
except Exception as e:
    check("live module test", False, f"{type(e).__name__}: {e}")

passed = sum(1 for _, ok, _ in checks if ok)
total = len(checks)
print(f"\n{passed}/{total} checks passed")
if passed < total:
    print("\nFAILED CHECKS:")
    for name, ok, detail in checks:
        if not ok:
            print(f"  - {name} {detail}")
    sys.exit(1)
print("ALL PASS")
