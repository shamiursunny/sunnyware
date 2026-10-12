# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Browser form fill + submit tool (Part 63)."""


class BrowserFillSubmitTool:
    name = "browser_fill_submit"
    description = (
        "Open a URL, fill one or more form fields (CSS selector -> value), "
        "then submit by clicking a button selector or pressing Enter. "
        "Returns the resulting page. Use for search forms, login forms "
        "(with user-provided tokens only — never store passwords), or any "
        "multi-field POST workflow."
    )
    parameters = {
        "url": {"type": "string", "required": True, "description": "Form URL"},
        "fields": {
            "type": "object",
            "required": True,
            "description": "Map of CSS selector -> value to fill",
        },
        "submit_selector": {
            "type": "string",
            "required": False,
            "description": "CSS selector of submit button (else press Enter)",
        },
        "wait_ms": {"type": "integer", "required": False, "description": "Extra wait after submit (default 1500)"},
        "max_chars": {"type": "integer", "required": False, "description": "HTML cap (default 60000)"},
    }

    async def run(self, args: dict) -> dict:
        from ._browser_session import validate_url as _v, new_context
        url = (args.get("url") or "").strip()
        err = _v(url)
        if err: return {"error": err}
        fields = args.get("fields") or {}
        if not isinstance(fields, dict) or not fields:
            return {"error": "fields must be a non-empty object"}
        if len(fields) > 20:
            return {"error": "too many fields (max 20)"}
        try:
            wait_ms = max(0, min(int(args.get("wait_ms") or 1500), 15000))
            max_chars = max(1000, min(int(args.get("max_chars") or 60000), 300000))
        except (TypeError, ValueError):
            return {"error": "numeric args must be integers"}
        submit_sel = (args.get("submit_selector") or "").strip()

        ctx = None
        try:
            ctx = await new_context()
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            for sel, val in fields.items():
                try:
                    await page.fill(str(sel), str(val), timeout=8000)
                except Exception as e:
                    return {"error": f"fill '{sel}' failed: {type(e).__name__}: {e}"}
            if submit_sel:
                btn = await page.query_selector(submit_sel)
                if not btn:
                    return {"error": f"submit selector not found: {submit_sel}"}
                await btn.click(timeout=8000)
            else:
                try:
                    await page.keyboard.press("Enter")
                except Exception:
                    pass
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
            "fields_filled": len(fields),
            "html": html[:max_chars],
            "html_chars": len(html),
            "truncated": len(html) > max_chars,
        }
