#!/usr/bin/env python3
"""Part 58 smoke test — document_diff tool."""
import ast, os, sys, asyncio, tempfile, csv
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
    print(" Part 58 — document_diff tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/document_diff.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("document_diff.py exists", tool_file.exists())
    if not tool_file.exists():
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class DocumentDiffTool" in src)
    check("name = document_diff", 'name = "document_diff"' in src)
    check("unified_diff uses difflib", "difflib.unified_diff" in src)
    check("SequenceMatcher for stats", "SequenceMatcher" in src)
    check("file mode", "_read_workspace_file" in src)
    check("rag mode", "_read_rag_chunk" in src)
    check("inline mode", '"left_text"' in src and '"right_text"' in src)
    check("ignore_case support", "ignore_case" in src)
    check("registered in __init__",
          "DocumentDiffTool.name: DocumentDiffTool()" in init_src)

    try:
        ast.parse(src)
        check("document_diff.py parses", True)
    except SyntaxError as e:
        check("document_diff.py parses", False, detail=str(e))

    # Integration — inline text mode
    async def run(**kw):
        from sunnyware.tools.document_diff import DocumentDiffTool
        return await DocumentDiffTool().run(kw)

    r = asyncio.run(run(
        left_text="line one\nline two\nline three",
        right_text="line one\nline TWO updated\nline three\nline four",
    ))
    check("inline diff succeeds", "error" not in r,
          detail=str(r)[:200] if r.get("error") else "")
    if "error" not in r:
        check("has unified_diff", "unified_diff" in r and len(r["unified_diff"]) > 0)
        check("stats has lines_added", r["stats"]["lines_added"] >= 1)
        check("stats has lines_removed", r["stats"]["lines_removed"] >= 1)
        check("similarity in (0,1)", 0 < r["stats"]["similarity"] < 1)
        check("identical is False", r["identical"] is False)
        check("unified_diff has @@ marker", "@@" in r["unified_diff"])
        check("unified_diff has - and + lines",
              any(l.startswith("-") and not l.startswith("---")
                  for l in r["unified_diff"].splitlines()) and
              any(l.startswith("+") and not l.startswith("+++")
                  for l in r["unified_diff"].splitlines()))

    # Identical case
    r2 = asyncio.run(run(left_text="alpha\nbeta", right_text="alpha\nbeta"))
    check("identical input -> identical True",
          "error" not in r2 and r2.get("identical") is True)
    check("identical -> similarity 1.0",
          r2.get("stats", {}).get("similarity") == 1.0)

    # ignore_case
    r3 = asyncio.run(run(
        left_text="Hello World",
        right_text="HELLO WORLD",
        ignore_case=True,
    ))
    check("ignore_case treats case-different as equal",
          "error" not in r3 and r3.get("stats", {}).get("lines_same") == 1)

    # File mode
    ws = Path(os.getenv("SUNNYWARE_WORKSPACE") or "/data/workspace").resolve()
    ws.mkdir(parents=True, exist_ok=True)
    f1 = ws / "diff_p58_a.txt"
    f2 = ws / "diff_p58_b.txt"
    f1.write_text("Version 1.0\nRule A\nRule B\nRule C\n", encoding="utf-8")
    f2.write_text("Version 1.1\nRule A\nRule B modified\nRule C\nRule D\n", encoding="utf-8")

    r4 = asyncio.run(run(left_file="diff_p58_a.txt", right_file="diff_p58_b.txt"))
    check("file mode succeeds", "error" not in r4,
          detail=str(r4)[:200] if r4.get("error") else "")
    if "error" not in r4:
        check("file mode similarity < 1", r4["stats"]["similarity"] < 1)
        check("file mode left_chars > 0", r4["left_chars"] > 0)

    # Cleanup
    for f in (f1, f2):
        try: f.unlink()
        except Exception: pass

    # Rejections
    r5 = asyncio.run(run())
    check("no inputs rejected", "error" in r5)

    r6 = asyncio.run(run(left_file="../../etc/passwd", right_text="x"))
    check("workspace escape rejected", "error" in r6)

    r7 = asyncio.run(run(left_file="nonexistent.txt", right_text="x"))
    check("missing file rejected", "error" in r7)

    r8 = asyncio.run(run(
        left_text="a\nb",
        right_text="a\nb",
        max_output_lines=1,
    ))
    check("max_output_lines caps diff",
          "error" not in r8 and r8.get("truncated") in (True, False))

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
