#!/usr/bin/env python3
"""Part 52 smoke test — citation_lookup tool."""
import ast, sys, asyncio
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
    print(" Part 52 — citation_lookup tool")
    print("=" * 62)

    tool_file = ROOT / "src/sunnyware/tools/citation_lookup.py"
    init_file = ROOT / "src/sunnyware/tools/__init__.py"

    check("citation_lookup.py exists", tool_file.exists())
    check("tools/__init__.py exists", init_file.exists())
    if not (tool_file.exists() and init_file.exists()):
        return 1

    src = tool_file.read_text(encoding="utf-8")
    init_src = init_file.read_text(encoding="utf-8")

    check("class defined", "class CitationLookupTool" in src)
    check("name = citation_lookup", 'name = "citation_lookup"' in src)
    check("exact mode params", '"source"' in src and '"chunk_id"' in src)
    check("search mode param", '"query"' in src)
    check("sha256 helper", "_sha256" in src and "hashlib" in src)
    check("returns full text (not preview)",
          '"text": text' in src and "preview" not in src)
    check("registered in __init__",
          "CitationLookupTool.name: CitationLookupTool()" in init_src)

    try:
        ast.parse(src)
        check("citation_lookup.py parses", True)
    except SyntaxError as e:
        check("citation_lookup.py parses", False, detail=str(e))

    # Integration
    async def run(**kw):
        from sunnyware.tools.citation_lookup import CitationLookupTool
        return await CitationLookupTool().run(kw)

    r_none = asyncio.run(run())
    # Local MINGW has no vector store; HF does. Accept both:
    #  - error    -> store has data, but caller gave no args
    #  - note     -> store is empty locally
    check("no args -> error or empty-store note",
          "error" in r_none or "note" in r_none)

    r_search = asyncio.run(run(query="attention", k=2))
    check("search mode returns results list",
          "results" in r_search and isinstance(r_search.get("results"), list))
    if r_search.get("count", 0) > 0:
        top = r_search["results"][0]
        check("search result has text field", "text" in top and len(top["text"]) > 0)
        check("search result has sha256_16", "sha256_16" in top and len(top["sha256_16"]) == 16)
        check("search result has source", "source" in top)

        # Now do exact lookup on that chunk
        r_exact = asyncio.run(run(source=top["source"], chunk_id=top["chunk_id"]))
        check("exact mode returns 1 result", r_exact.get("count") == 1)
        if r_exact.get("count") == 1:
            e = r_exact["results"][0]
            check("exact text matches search text", e["text"] == top["text"])
            check("exact hash matches search hash", e["sha256_16"] == top["sha256_16"])
            check("exact mode label", r_exact.get("mode") == "exact")

    r_miss = asyncio.run(run(source="does-not-exist.pdf", chunk_id=0))
    check("missing chunk returns error/count 0",
          r_miss.get("count") == 0 or "error" in r_miss)

    print()
    print("=" * 62)
    print(f" RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
