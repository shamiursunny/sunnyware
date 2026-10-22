# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""HTML to clean text/markdown (Part 78).

Converts HTML to readable text with structure preserved:
headings, paragraphs, lists, links, code blocks. Better than a plain
regex strip for articles — this keeps the readable flow.

Uses stdlib html.parser — no new deps.
"""
import re
from html.parser import HTMLParser


_MAX_INPUT = 1_000_000
_BLOCK_TAGS = {
    "p", "div", "section", "article", "header", "footer", "main", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr",
    "ul", "ol", "li", "blockquote", "pre", "tr", "table",
}
_SKIP_TAGS = {"script", "style", "noscript", "iframe", "svg", "head"}


class _HtmlToMd(HTMLParser):
    def __init__(self, keep_links: bool = True):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip_depth = 0
        self.keep_links = keep_links
        self.list_stack = []  # ("ul"|"ol", counter)
        self.link_href = None
        self.in_pre = 0
        self.heading_level = 0

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in _SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if t == "br":
            self.out.append("\n")
        elif t == "hr":
            self.out.append("\n\n---\n\n")
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            lvl = int(t[1])
            self.out.append("\n\n" + ("#" * lvl) + " ")
            self.heading_level = lvl
        elif t == "p":
            self.out.append("\n\n")
        elif t == "li":
            if self.list_stack:
                kind, counter = self.list_stack[-1]
                if kind == "ol":
                    counter += 1
                    self.list_stack[-1] = (kind, counter)
                    self.out.append("\n" + str(counter) + ". ")
                else:
                    self.out.append("\n- ")
            else:
                self.out.append("\n- ")
        elif t in ("ul", "ol"):
            self.list_stack.append((t, 0))
            self.out.append("\n")
        elif t == "blockquote":
            self.out.append("\n\n> ")
        elif t == "pre":
            self.in_pre += 1
            self.out.append("\n\n```\n")
        elif t == "code" and not self.in_pre:
            self.out.append("`")
        elif t == "a" and self.keep_links:
            for k, v in attrs:
                if k.lower() == "href" and v:
                    self.link_href = v
                    break
            self.out.append("[")
        elif t in ("strong", "b"):
            self.out.append("**")
        elif t in ("em", "i"):
            self.out.append("*")
        elif t == "tr":
            self.out.append("\n")
        elif t in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in _SKIP_TAGS:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if t in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
            self.out.append("\n")
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.out.append("\n")
            self.heading_level = 0
        elif t == "p":
            self.out.append("\n\n")
        elif t == "pre":
            if self.in_pre:
                self.in_pre -= 1
            self.out.append("\n```\n\n")
        elif t == "code" and not self.in_pre:
            self.out.append("`")
        elif t == "a" and self.keep_links:
            href = self.link_href or ""
            self.out.append("](" + href + ")")
            self.link_href = None
        elif t in ("strong", "b"):
            self.out.append("**")
        elif t in ("em", "i"):
            self.out.append("*")

    def handle_data(self, data):
        if self.skip_depth or not data:
            return
        if self.in_pre:
            self.out.append(data)
        else:
            self.out.append(re.sub(r"\s+", " ", data))

    def result(self) -> str:
        s = "".join(self.out)
        # collapse excessive blank lines
        s = re.sub(r"\n{3,}", "\n\n", s)
        # trim leading/trailing space on each line
        lines = [ln.strip() for ln in s.split("\n")]
        s = "\n".join(lines).strip()
        return s


class HtmlToTextTool:
    name = "html_to_text"
    description = "Strip HTML tags to extract plain text. Triggers: HTML to text, strip HTML, extract text from HTML. Input: HTML string. Returns plain text." into clean, readable "
        "markdown-style text. Preserves headings, paragraphs, lists, links, "
        "code blocks. Better than web_fetch for articles because structure "
        "is kept. Provide either raw 'html' string or a 'url' to fetch."
    )
    parameters = {
        "url": {"type": "string", "required": False,
                "description": "URL to fetch and convert (blocked: private hosts)"},
        "html": {"type": "string", "required": False,
                 "description": "Raw HTML string to convert"},
        "keep_links": {"type": "boolean", "required": False,
                       "description": "Keep link URLs as [text](url) (default true)"},
        "max_chars": {"type": "integer", "required": False,
                      "description": "Cap output chars (default 40000, max 200000)"},
    }

    async def run(self, args: dict) -> dict:
        try:
            max_chars = int(args.get("max_chars") or 40000)
        except (TypeError, ValueError):
            max_chars = 40000
        max_chars = max(500, min(max_chars, 200000))
        keep_links = bool(args.get("keep_links", True))

        html = args.get("html")
        source = None

        if not html:
            url = (args.get("url") or "").strip()
            if not url:
                return {"error": "provide either 'url' or 'html'"}
            try:
                from .api_call import _check_url
                err = _check_url(url)
            except Exception:
                err = None if url.startswith(("http://", "https://")) else "url must be http(s)"
            if err:
                return {"error": err}
            try:
                import httpx
            except Exception:
                return {"error": "httpx not available for URL fetching"}
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    r = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (compatible; sunnyware/1.0)"
                    })
            except Exception as e:
                return {"error": type(e).__name__ + ": " + str(e)[:200]}
            if r.status_code != 200:
                return {"error": "HTTP " + str(r.status_code), "url": str(r.url)}
            html = r.content[:_MAX_INPUT].decode(r.encoding or "utf-8", errors="replace")
            source = str(r.url)

        html = str(html)[:_MAX_INPUT]

        try:
            parser = _HtmlToMd(keep_links=keep_links)
            parser.feed(html)
            parser.close()
            text = parser.result()
        except Exception as e:
            return {"error": "parse failed: " + type(e).__name__ + ": " + str(e)[:200]}

        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + "\n\n... [truncated]"

        return {
            "source": source,
            "input_chars": len(html),
            "output_chars": len(text),
            "truncated": truncated,
            "text": text,
        }
