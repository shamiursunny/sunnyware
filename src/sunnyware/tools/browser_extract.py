# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Browser extract tool (Part 63). CSS selector -> structured rows."""


class BrowserExtractTool:
    name = "browser_extract"
    description = (
        "Open a URL in headless Chromium, run a CSS selector, and return "
        "structured rows. For each matched element, returns its text, "
        "href, src, and any requested attributes. Use this for JS-rendered "
        "lists, tables, cards, or search results."
    )
    parameters = {
        "url": {"type": "string", "description": "http(s) URL", "required": True},
        "selector": {"type": "string", "description": "CSS selector (e.g. '.result', 'table tr')", "required": True},
        "attributes": {"type": "array", "description": "Extra attributes to extract (e.g. ['href','data-id'])", "required": False},
        "limit": {"type": "integer", "description": "Max rows (default 50, max 500)", "required": False},
        "wait_ms": {"type": "integer", "description": "Extra wait after load (ms)", "required": False},
    }

    async def run(self, args: dict) -> dict:
        from ._browser_session import validate_url as _v, new_context
        url = (args.get("url") or "").strip()
        selector = (args.get("selector") or "").strip()
        err = _v(url)
        if err: return {"error": err}
        if not selector: return {"error": "selector is required"}
        try:
            limit = max(1, min(int(args.get("limit") or 50), 500))
            wait_ms = max(0, min(int(args.get("wait_ms") or 0), 10000))
        except (TypeError, ValueError):
            return {"error": "limit/wait_ms must be integers"}
        attrs = args.get("attributes") or []
        if not isinstance(attrs, list):
            attrs = []
        attrs = [str(a) for a in attrs][:10]

        ctx = None
        try:
            ctx = await new_context()
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_ms:
                await page.wait_for_timeout(wait_ms)
            elements = await page.query_selector_all(selector)
            title = await page.title()
            rows = []
            for el in elements[:limit]:
                try:
                    text = (await el.inner_text()) or ""
                except Exception:
                    text = ""
                row = {"text": text.strip()[:2000]}
                try:
                    row["href"] = await el.get_attribute("href")
                except Exception:
                    pass
                try:
                    row["src"] = await el.get_attribute("src")
                except Exception:
                    pass
                for a in attrs:
                    try:
                        row[a] = await el.get_attribute(a)
                    except Exception:
                        row[a] = None
                rows.append(row)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        finally:
            if ctx:
                try: await ctx.close()
                except Exception: pass

        return {
            "url": url,
            "title": title,
            "selector": selector,
            "count": len(rows),
            "truncated": len(elements) > limit,
            "rows": rows,
        }
