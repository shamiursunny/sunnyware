# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Browser navigation tool (Part 63). Renders JS, returns final HTML."""


class BrowserGotoTool:
    name = "browser_goto"
    description = (
        "Open a URL in a headless Chromium browser, wait for JavaScript "
        "to render, and return the final HTML + title + status. Use this "
        "instead of web_fetch for JS-heavy sites (SPAs, dashboards, "
        "infinite scroll). Private hosts are blocked. First call after a "
        "cold start may take 3-5 minutes while the browser binary installs."
    )
    parameters = {
        "url": {"type": "string", "description": "http(s) URL", "required": True},
        "wait_for": {"type": "string", "description": "CSS selector to wait for", "required": False},
        "wait_ms": {"type": "integer", "description": "Extra ms to wait after load (default 0)", "required": False},
        "max_chars": {"type": "integer", "description": "Cap HTML chars (default 80000)", "required": False},
    }

    async def run(self, args: dict) -> dict:
        url = (args.get("url") or "").strip()
        err = validate_url(url) if 'validate_url' in dir() else None
        from ._browser_session import validate_url as _v, new_context
        err = _v(url)
        if err:
            return {"error": err}
        try:
            wait_ms = max(0, min(int(args.get("wait_ms") or 0), 10000))
        except (TypeError, ValueError):
            wait_ms = 0
        try:
            max_chars = max(1000, min(int(args.get("max_chars") or 80000), 500000))
        except (TypeError, ValueError):
            max_chars = 80000
        wait_for = (args.get("wait_for") or "").strip()

        ctx = None
        try:
            ctx = await new_context()
            page = await ctx.new_page()
            resp = await page.goto(url, wait_until="domcontentloaded",
                                   timeout=30000)
            if wait_for:
                try:
                    await page.wait_for_selector(wait_for, timeout=15000)
                except Exception:
                    pass
            if wait_ms:
                await page.wait_for_timeout(wait_ms)
            html = await page.content()
            title = await page.title()
            status = resp.status if resp else None
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        finally:
            if ctx:
                try:
                    await ctx.close()
                except Exception:
                    pass

        truncated = len(html) > max_chars
        return {
            "url": url,
            "status": status,
            "title": title,
            "html": html[:max_chars],
            "html_chars": len(html),
            "truncated": truncated,
        }
