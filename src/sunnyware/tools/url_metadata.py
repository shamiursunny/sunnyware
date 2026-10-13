# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""URL metadata extractor (Part 78).

Fetch a URL, parse <meta> tags + title + favicon. Returns OpenGraph,
Twitter Card, and standard metadata. Reuses api_call SSRF guard.
"""
import re
from urllib.parse import urljoin, urlparse

try:
    import httpx
    _HAS = True
except Exception:
    _HAS = False


_MAX_HTML_BYTES = 500_000
_TIMEOUT = 12.0


def _find_meta(html: str, key: str, attr: str = "property") -> str:
    """Find <meta property="og:title" content="..."> style tag."""
    pattern = (
        r"<meta\s+[^>]*" + re.escape(attr) + r"=[\"']" + re.escape(key) +
        r"[\"'][^>]*content=[\"']([^\"']*)[\"']"
    )
    m = re.search(pattern, html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Also try the reverse order (content= before property=)
    pattern2 = (
        r"<meta\s+[^>]*content=[\"']([^\"']*)[\"'][^>]*" +
        re.escape(attr) + r"=[\"']" + re.escape(key) + r"[\"']"
    )
    m = re.search(pattern2, html, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _find_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _find_favicon(html: str, base_url: str) -> str:
    m = re.search(
        r"<link[^>]*rel=[\"'](?:icon|shortcut icon)[\"'][^>]*href=[\"']([^\"']*)[\"']",
        html, re.IGNORECASE,
    )
    if m:
        return urljoin(base_url, m.group(1).strip())
    return urljoin(base_url, "/favicon.ico")


class UrlMetadataTool:
    name = "url_metadata"
    description = (
        "Fetch a URL and extract its metadata: <title>, OpenGraph "
        "(og:title, og:description, og:image, og:url, og:site_name, "
        "og:type), Twitter Card, standard description/keywords, "
        "canonical URL, and favicon. Use when the user shares a link and "
        "you need to describe it. Private hosts are blocked."
    )
    parameters = {
        "url": {"type": "string", "required": True, "description": "http(s) URL"},
    }

    async def run(self, args: dict) -> dict:
        if not _HAS:
            return {"error": "httpx not available"}
        url = (args.get("url") or "").strip()
        try:
            from .api_call import _check_url
            err = _check_url(url)
        except Exception:
            err = None if url.startswith(("http://", "https://")) else "url must be http(s)"
        if err:
            return {"error": err}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT,
                                          follow_redirects=True) as client:
                r = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; sunnyware/1.0)"
                })
        except httpx.TimeoutException:
            return {"error": "timeout after " + str(_TIMEOUT) + "s"}
        except Exception as e:
            return {"error": type(e).__name__ + ": " + str(e)[:200]}

        if r.status_code != 200:
            return {"error": "HTTP " + str(r.status_code), "url": str(r.url)}

        raw = r.content[:_MAX_HTML_BYTES]
        ct = (r.headers.get("content-type") or "").lower()
        try:
            html = raw.decode(r.encoding or "utf-8", errors="replace")
        except Exception:
            html = raw.decode("utf-8", errors="replace")

        base = str(r.url)
        result = {
            "url": base,
            "status": r.status_code,
            "content_type": ct,
            "title": _find_title(html),
            "description": _find_meta(html, "description", "name"),
            "keywords": _find_meta(html, "keywords", "name"),
            "author": _find_meta(html, "author", "name"),
            "canonical": "",
            "favicon": _find_favicon(html, base),
            "og": {
                "title": _find_meta(html, "og:title"),
                "description": _find_meta(html, "og:description"),
                "image": _find_meta(html, "og:image"),
                "url": _find_meta(html, "og:url"),
                "type": _find_meta(html, "og:type"),
                "site_name": _find_meta(html, "og:site_name"),
            },
            "twitter": {
                "card": _find_meta(html, "twitter:card", "name"),
                "title": _find_meta(html, "twitter:title", "name"),
                "description": _find_meta(html, "twitter:description", "name"),
                "image": _find_meta(html, "twitter:image", "name"),
            },
        }
        m = re.search(
            r"<link[^>]*rel=[\"']canonical[\"'][^>]*href=[\"']([^\"']*)[\"']",
            html, re.IGNORECASE,
        )
        if m:
            result["canonical"] = urljoin(base, m.group(1).strip())
        return result
