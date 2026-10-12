# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Browser click tool (Part 63). Click element, return new state."""


class BrowserClickTool:
    name = "browser_click"
    description = (
        "Open a URL, click an element (by CSS selector), then return the "
        "resulting page HTML + title + URL. Waits for network idle after "
        "the click. Use for multi-step navigation (pagination, tabs, "
        "expand/collapse, 'next page')."
    )
    parameters = {
        "url": {"type": "string", "required": True, "description": "Starting URL"},
        "selector": {"type": "string", "required": True, "description": "CSS selector of element to click"},
        "wait_ms": {"type": "integer", "required": False, "description": "Extra wait after click (ms)"},
        "max_chars": {"type": "integer", "required": False, "description": "HTML cap (default 60000)"},
    }

    async def run(self, args: dict) -> dict:
        from ._browser_session import validate_url as _v, new_context
        url = (args.get("url") or "").strip()
        selector = (args.get("selector") or "").strip()
        err = _v(url)
        if err: return {"error": err}
        if not selector: return {"error": "selector is required"}
        try:
            wait_ms = max(0, min(int(args.get("wait_ms") or 1000), 10000))
            max_chars = max(1000, min(int(args.get("max_chars") or 60000), 300000))
        except (TypeError, ValueError):
            return {"error": "numeric args must be integers"}

        ctx = None
        try:
            ctx = await new_context()
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            el = await page.query_selector(selector)
            if not el:
                return {"error": f"selector not found: {selector}"}
            try:
                await el.click(timeout=10000)
            except Exception as e:
                return {"error": f"click failed: {type(e).__name__}: {e}"}
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            if wait_ms:
                await page.wait_for_timeout(wait_ms)
            html = await page.content()
            title = await page.title()
            final_url = page.url
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        finally:
            if ctx:
                try: await ctx.close()
                except Exception: pass

        return {
            "start_url": url,
            "final_url": final_url,
            "title": title,
            "html": html[:max_chars],
            "html_chars": len(html),
            "truncated": len(html) > max_chars,
        }
