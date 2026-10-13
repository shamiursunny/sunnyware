#!/usr/bin/env python3
"""Part 78 smoke test - url_metadata + html_to_text."""
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
        PASS += 1; print("  [PASS] " + label)
    else:
        FAIL += 1; print("  [FAIL] " + label + (" - " + detail if detail else ""))


def main():
    print("=" * 62)
    print(" Part 78 - url_metadata + html_to_text")
    print("=" * 62)

    init_src = (ROOT / "src/sunnyware/tools/__init__.py").read_text(encoding="utf-8")

    for mod, cls in [("url_metadata", "UrlMetadataTool"),
                     ("html_to_text", "HtmlToTextTool")]:
        f = ROOT / "src" / "sunnyware" / "tools" / (mod + ".py")
        check(mod + ".py exists", f.exists())
        if not f.exists(): continue
        s = f.read_text(encoding="utf-8")
        check(mod + " class", "class " + cls in s)
        check(mod + " registered", cls + ".name: " + cls + "()" in init_src)
        try:
            ast.parse(s); check(mod + " parses", True)
        except SyntaxError as e:
            check(mod + " parses", False, detail=str(e))

    # Unit tests: url_metadata regex helpers
    from sunnyware.tools.url_metadata import _find_meta, _find_title, _find_favicon
    html = '<html><head><title>Test Page</title>'
    html += '<meta property="og:title" content="OG Title">'
    html += '<meta property="og:description" content="OG Desc">'
    html += '<meta name="description" content="Desc">'
    html += '<link rel="icon" href="/fav.png">'
    html += '</head></html>'
    check("title extracted", _find_title(html) == "Test Page")
    check("og:title extracted", _find_meta(html, "og:title") == "OG Title")
    check("og:description extracted", _find_meta(html, "og:description") == "OG Desc")
    check("name-description extracted",
          _find_meta(html, "description", "name") == "Desc")
    check("favicon absolute", "example.com/fav.png" in _find_favicon(html, "https://example.com/x"))

    # Unit tests: html_to_text conversion
    from sunnyware.tools.html_to_text import _HtmlToMd
    h2t = '<h1>Hello</h1><p>World <strong>bold</strong> <a href="https://x.com">link</a></p>'
    h2t += '<ul><li>one</li><li>two</li></ul>'
    parser = _HtmlToMd(keep_links=True)
    parser.feed(h2t); parser.close()
    md = parser.result()
    check("h1 -> # heading", "# Hello" in md, detail=md[:80])
    check("p preserved", "World" in md)
    check("bold -> **bold**", "**bold**" in md)
    check("link -> [link](url)", "[link](https://x.com)" in md)
    check("ul -> - items", "- one" in md and "- two" in md)
    check("no html tags left", "<" not in md and ">" not in md)

    # html_to_text skips script/style
    parser2 = _HtmlToMd()
    parser2.feed("<p>Keep</p><script>var x=1;</script><style>.c{}</style><p>End</p>")
    parser2.close()
    md2 = parser2.result()
    check("script stripped", "var x" not in md2)
    check("style stripped", ".c{" not in md2)
    check("content preserved", "Keep" in md2 and "End" in md2)

    # Rejections
    async def run_um(**kw):
        from sunnyware.tools.url_metadata import UrlMetadataTool
        return await UrlMetadataTool().run(kw)
    async def run_h2t(**kw):
        from sunnyware.tools.html_to_text import HtmlToTextTool
        return await HtmlToTextTool().run(kw)

    check("url_metadata blocks localhost",
          "error" in asyncio.run(run_um(url="http://localhost:8080")))
    check("url_metadata blocks 10.x",
          "error" in asyncio.run(run_um(url="http://10.0.0.5/x")))
    check("url_metadata no url rejected",
          "error" in asyncio.run(run_um()))
    check("html_to_text no input rejected",
          "error" in asyncio.run(run_h2t()))
    check("html_to_text blocks localhost url",
          "error" in asyncio.run(run_h2t(url="http://127.0.0.1")))

    print()
    print("=" * 62)
    print(" RESULT: " + str(PASS) + " passed, " + str(FAIL) + " failed")
    print("=" * 62)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
