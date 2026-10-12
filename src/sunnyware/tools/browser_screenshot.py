# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Browser screenshot tool (Part 63). Returns PNG base64 + saves to workspace."""
import base64
import os
from datetime import datetime
from pathlib import Path


_MAX_BYTES = 5 * 1024 * 1024


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


class BrowserScreenshotTool:
    name = "browser_screenshot"
    description = (
        "Open a URL in headless Chromium and capture a PNG screenshot. "
        "Returns base64 + saves a copy to /data/workspace/. Supports "
        "full_page (default true) and a CSS selector to crop. Private "
        "hosts are blocked."
    )
    parameters = {
        "url": {"type": "string", "description": "http(s) URL", "required": True},
        "full_page": {"type": "boolean", "description": "Capture full page (default true)", "required": False},
        "selector": {"type": "string", "description": "Screenshot only this CSS element", "required": False},
        "wait_ms": {"type": "integer", "description": "Extra wait after load (ms)", "required": False},
        "viewport_width": {"type": "integer", "description": "Viewport width (default 1280)", "required": False},
        "viewport_height": {"type": "integer", "description": "Viewport height (default 800)", "required": False},
        "filename": {"type": "string", "description": "Save filename (default auto)", "required": False},
    }

    async def run(self, args: dict) -> dict:
        from ._browser_session import validate_url as _v, get_browser
        url = (args.get("url") or "").strip()
        err = _v(url)
        if err:
            return {"error": err}
        try:
            wait_ms = max(0, min(int(args.get("wait_ms") or 0), 10000))
            vw = max(320, min(int(args.get("viewport_width") or 1280), 4000))
            vh = max(240, min(int(args.get("viewport_height") or 800), 4000))
        except (TypeError, ValueError):
            return {"error": "numeric args must be integers"}
        full_page = bool(args.get("full_page", True))
        selector = (args.get("selector") or "").strip()

        browser = await get_browser()
        ctx = None
        try:
            ctx = await browser.new_context(
                viewport={"width": vw, "height": vh},
                ignore_https_errors=True,
            )
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_ms:
                await page.wait_for_timeout(wait_ms)
            if selector:
                el = await page.query_selector(selector)
                if not el:
                    return {"error": f"selector not found: {selector}"}
                png = await el.screenshot(type="png")
            else:
                png = await page.screenshot(type="png", full_page=full_page)
            title = await page.title()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        finally:
            if ctx:
                try: await ctx.close()
                except Exception: pass

        if len(png) > _MAX_BYTES:
            return {"error": f"screenshot too large: {len(png)} bytes > {_MAX_BYTES}"}

        name = (args.get("filename") or "").strip()
        if not name:
            ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            name = f"screenshot-{ts}.png"
        name = "".join(c if (c.isalnum() or c in "._-") else "_" for c in name)
        if not name.lower().endswith(".png"):
            name += ".png"
        name = name[:120]
        root = _workspace_root()
        try:
            root.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(png)
            saved_path = str((root / name).resolve())
        except Exception as e:
            saved_path = None

        return {
            "url": url,
            "title": title,
            "bytes": len(png),
            "saved_path": saved_path,
            "image_base64": base64.b64encode(png).decode("ascii"),
            "image_format": "png",
        }
