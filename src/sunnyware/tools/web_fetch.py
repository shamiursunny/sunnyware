# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Fetch URL and return text (basic HTML strip)."""

import re
import httpx


MAX_BYTES = 512 * 1024  # 512 KB
MAX_CHARS_RETURNED = 8000


_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    html = _SCRIPT_STYLE.sub(" ", html)
    text = _TAG.sub(" ", html)
    text = _WS.sub(" ", text).strip()
    return text


class WebFetchTool:
    name = "web_fetch"
    description = "Fetch a URL (http/https) and return a text summary. HTML is stripped to plain text."
    parameters = {
        "url": {
            "type": "string",
            "description": "Full URL to fetch (must start with http:// or https://)",
            "required": True,
        }
    }

    async def run(self, args: dict) -> dict:
        url = str(args.get("url", "")).strip()
        if not url:
            return {"error": "url is required"}
        if not (url.startswith("http://") or url.startswith("https://")):
            return {"error": "only http/https URLs allowed"}

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": "Sunnyware/0.1 (+agent)"},
            ) as client:
                r = await client.get(url)
                raw = r.content[:MAX_BYTES]
                encoding = r.encoding or "utf-8"
                try:
                    html = raw.decode(encoding, errors="replace")
                except Exception:
                    html = raw.decode("utf-8", errors="replace")
        except Exception as e:
            return {"error": f"fetch failed: {type(e).__name__}: {e}"}

        content_type = r.headers.get("content-type", "")
        if "html" in content_type.lower():
            text = _strip_html(html)
        else:
            text = html

        truncated = len(text) > MAX_CHARS_RETURNED
        text = text[:MAX_CHARS_RETURNED]

        return {
            "url": str(r.url),
            "status": r.status_code,
            "content_type": content_type,
            "text": text,
            "truncated": truncated,
            "bytes_received": len(r.content),
        }
