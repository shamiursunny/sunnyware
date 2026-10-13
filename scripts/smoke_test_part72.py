#!/usr/bin/env python3
"""Part 72 smoke test - pdf_read tool."""
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
        PASS += 1; print("  [PASS] " + label)
    else:
        FAIL += 1; print("  [FAIL] " + label + (" - " + detail if detail else ""))


def main():
    print("=" * 62)
    print(" Part 72 - pdf_read tool")
    print("=" * 62)

    f = ROOT / "src/sunnyware/tools/pdf_read.py"
    check("pdf_read.py exists", f.exists())
    if not f.exists():
        return 1

    src = f.read_text(encoding="utf-8")
    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")

    check("class defined", "class PdfReadTool" in src)
    check("name = pdf_read", 'name = "pdf_read"' in src)
    check("uses PdfReader", "PdfReader" in src)
    check("workspace jail", "_workspace_root" in src)
    check("char cap", "_MAX_CHARS" in src)
    check("page filter", '"pages"' in src)
    check("table extraction", "extract_tables" in src)
    check("registered", "PdfReadTool.name: PdfReadTool()" in init_src)

    try:
        ast.parse(src); check("pdf_read.py parses", True)
    except SyntaxError as e:
        check("pdf_read.py parses", False, detail=str(e))

    # Build a small PDF
    ws = Path(os.getenv("SUNNYWARE_WORKSPACE") or "/data/workspace").resolve()
    ws.mkdir(parents=True, exist_ok=True)
    test_pdf = ws / "smoke_p72.pdf"
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
        with PdfPages(str(test_pdf)) as pdf:
            for i in range(3):
                fig = plt.figure(figsize=(6, 4))
                fig.text(0.1, 0.5, "Page " + str(i+1) + " - Sunnyware Part 72",
                         fontsize=14)
                pdf.savefig(fig); plt.close(fig)
        check("test PDF written", test_pdf.exists())
    except Exception as e:
        check("test PDF written", False, detail=str(e))

    async def run(**kw):
        from sunnyware.tools.pdf_read import PdfReadTool
        return await PdfReadTool().run(kw)

    r = asyncio.run(run(file="smoke_p72.pdf"))
    check("read succeeds", "error" not in r,
          detail=str(r)[:200] if r.get("error") else "")
    if "error" not in r:
        check("total_pages == 3", r.get("total_pages") == 3,
              detail=str(r.get("total_pages")))
        check("pages_returned == 3", r.get("pages_returned") == 3)
        check("at least 1 page has text",
              any(p.get("chars", 0) > 0 for p in r.get("pages", [])))

    r2 = asyncio.run(run(file="smoke_p72.pdf", pages=[2]))
    check("page filter works", "error" not in r2 and r2.get("pages_returned") == 1)

    check("missing file rejected",
          "error" in asyncio.run(run(file="nope.pdf")))
    check("escape rejected",
          "error" in asyncio.run(run(file="../../etc/passwd")))
    check("non-pdf rejected",
          "error" in asyncio.run(run(file="notpdf.txt")))

    try: test_pdf.unlink()
    except Exception: pass

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
