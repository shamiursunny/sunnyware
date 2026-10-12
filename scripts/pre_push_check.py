#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Master pre-push check for Sunnyware (DevSecOps gate).

Runs BEFORE every commit + push:
  1. Python syntax check on every src/sunnyware/**/*.py
  2. Served HTML sanity (catches the webui.py escape-bug pattern)
  3. Latest smoke test (scripts/smoke_test_part*.py by highest part number)
  4. Git working-tree check (no unexpected junk / secrets)
  5. Live HF Space health check (soft warning only)

Exit code 0 = safe to push. Any failure = stop.
"""

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "sunnyware"
SCRIPTS = ROOT / "scripts"

PASS = 0
FAIL = 0
WARN = 0


def header(title):
    print()
    print("=" * 70)
    print(" " + title)
    print("=" * 70)


def ok(msg):
    global PASS
    PASS += 1
    print("  [PASS] " + msg)


def bad(msg):
    global FAIL
    FAIL += 1
    print("  [FAIL] " + msg)


def warn(msg):
    global WARN
    WARN += 1
    print("  [WARN] " + msg)


# ── Stage 1: Python syntax ──
def stage_syntax():
    header("1. Python syntax check")
    files = sorted(SRC.rglob("*.py"))
    print("  scanning " + str(len(files)) + " files...")
    errors = 0
    for f in files:
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            bad(f"{f.relative_to(ROOT)}: line {e.lineno}: {e.msg}")
            errors += 1
    if errors == 0:
        ok("all " + str(len(files)) + " Python files parse cleanly")


# ── Stage 2: Served HTML sanity (escape-bug detector) ──
def stage_webui_html():
    header("2. Served HTML / JS sanity check")
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from sunnyware import webui
    except Exception as e:
        bad("cannot import webui: " + type(e).__name__ + ": " + str(e))
        return
    html = webui.HTML
    print("  runtime HTML: " + str(len(html)) + " chars")

    # Detect unescaped newlines inside single-quoted JS strings
    # Heuristic: a single quote, then newline, then spaces, then more content on next line
    lines = html.splitlines()
    bugs = []
    for i, ln in enumerate(lines):
        stripped = ln.rstrip()
        # line ends with an open single-quote (odd count)
        single_quotes = stripped.count("'")
        double_quotes = stripped.count('"')
        if single_quotes % 2 == 1 and not stripped.endswith("\\'"):
            # odd number of single-quotes at line end -> probably opens a string
            # that never closes on this line (very likely the escape bug)
            if "//" not in stripped[-30:]:
                bugs.append((i + 1, stripped[-60:]))

    if bugs:
        for lineno, snippet in bugs[:5]:
            bad(f"line {lineno} ends with unclosed quote: ...{snippet!r}")
        warn(f"{len(bugs)} potential broken-string lines (manual review if listed)")
    else:
        ok("no obvious broken JS string literals detected")

    # Basic sanity — key markers present
    markers = ['id="chat"', 'id="sidebar"', 'id="newChatBtn"', 'sendMessage']
    missing = [m for m in markers if m not in html]
    if missing:
        warn("missing markers: " + ", ".join(missing))
    else:
        ok("all key HTML markers present")


# ── Stage 3: Latest part-specific smoke test ──
def stage_smoke_test():
    header("3. Part-specific smoke test")
    tests = sorted(SCRIPTS.glob("smoke_test_part*.py"))
    if not tests:
        warn("no smoke_test_partNN.py found — skipping (recommend adding one)")
        return
    # Highest part number
    def part_num(p):
        name = p.stem  # smoke_test_part39
        try:
            return int(name.rsplit("part", 1)[1])
        except Exception:
            return 0
    tests.sort(key=part_num)
    latest = tests[-1]
    print("  running: " + latest.name)
    r = subprocess.run(
        [sys.executable, str(latest)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    for ln in (r.stdout or "").splitlines():
        print("    " + ln)
    if r.returncode == 0:
        ok(latest.name + " passed")
    else:
        if r.stderr:
            print("    stderr:")
            for ln in r.stderr.splitlines()[:10]:
                print("      " + ln)
        bad(latest.name + " failed (exit " + str(r.returncode) + ")")


# ── Stage 4: Git working-tree check ──
def stage_git_status():
    header("4. Git working-tree check")
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        bad("git status failed: " + str(e))
        return
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    if not lines:
        ok("working tree clean — nothing to commit")
        return

    print("  changes:")
    suspicious = []
    secret_patterns = (".env", "id_rsa", ".pem", ".key", "credentials")
    junk_patterns = (".pyc", "__pycache__", ".bak", ".tmp", ".log", ".DS_Store")
    for ln in lines:
        print("    " + ln)
        low = ln.lower()
        if any(s in low for s in secret_patterns):
            suspicious.append(("secret", ln))
        if any(j in low for j in junk_patterns):
            suspicious.append(("junk", ln))

    if suspicious:
        for kind, ln in suspicious:
            bad(f"{kind} file in changeset: {ln}")
    else:
        ok(str(len(lines)) + " change(s), no secrets or junk detected")


# ── Stage 5: Live HF health (soft) ──
def stage_hf_health():
    header("5. Live HF Space health (soft check)")
    try:
        import httpx
    except ImportError:
        warn("httpx not installed — skipping live check")
        return
    try:
        r = httpx.get(
            "https://shamiur-sunnyware.hf.space/health/ready",
            timeout=10.0,
        )
        if r.status_code == 200:
            d = r.json()
            st = d.get("status")
            tools = (d.get("checks") or {}).get("tools")
            if st == "ok":
                ok("HF Space healthy · tools=" + str(tools))
            else:
                warn("HF Space returned status=" + str(st))
        else:
            warn("HF Space HTTP " + str(r.status_code) + " — may be mid-rebuild")
    except Exception as e:
        warn("HF Space unreachable: " + type(e).__name__ + " — push anyway")


# ── Run all stages ──
def main():
    print()
    print("#" * 70)
    print("# Sunnyware Pre-Push Check")
    print("#" * 70)
    stage_syntax()
    stage_webui_html()
    stage_smoke_test()
    stage_git_status()
    stage_hf_health()

    print()
    print("=" * 70)
    print(" SUMMARY: " + str(PASS) + " passed · " + str(FAIL) + " failed · " + str(WARN) + " warnings")
    print("=" * 70)
    if FAIL > 0:
        print()
        print("  RESULT: BLOCKED — fix failures before pushing.")
        print()
        return 1
    print()
    print("  RESULT: READY TO PUSH.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
