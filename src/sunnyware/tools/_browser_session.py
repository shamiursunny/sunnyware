# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Browser session manager with optimized launch args."""

import os
import stat
import subprocess
import urllib.parse
from playwright.async_api import async_playwright

_playwright = None
_browser = None

def validate_url(url: str) -> str | None:
    if not url.startswith(("http://", "https://")):
        return "URL must start with http:// or https://"
    return None

async def get_browser():
    global _playwright, _browser
    if _browser and _browser.is_connected():
        return _browser
    if not _playwright:
        _playwright = await async_playwright().start()
    
    # Aggressively fix EACCES (Permission Denied) across the entire directory
    try:
        if os.path.exists("/data/.cache/ms-playwright"):
            subprocess.run(["chmod", "-R", "+x", "/data/.cache/ms-playwright"], check=False, timeout=5)
    except Exception as e:
        print(f"[browser] chmod warning: {e}")

    args = [
        "--no-sandbox",
        "--no-zygote",                    # Fixes the startup hang
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",        # Prevents crashes on limited memory
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=IsolateOrigins,site-per-process"
    ]
    
    _browser = await _playwright.chromium.launch(headless=True, args=args)
    return _browser

async def new_context():
    browser = await get_browser()
    return await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
