# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Shared Playwright lifecycle (Part 63).

One Chromium process, many contexts. Lazy install of the browser
binary on first use, cached to /data/playwright-browsers so it
survives Space restarts.
"""
import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

_NAV_TIMEOUT_MS = 30000
_DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_browser = None
_playwright = None
_lock = asyncio.Lock()
_install_done = False


def _cache_dir() -> Path:
    p = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if p:
        return Path(p)
    return Path("/data/playwright-browsers")


def _browser_cached() -> bool:
    d = _cache_dir()
    if not d.exists():
        return False
    # Chromium folder naming: chromium-<rev>/
    return any(c.name.startswith("chromium-") for c in d.iterdir())


def _chmod_cache():
    """Best-effort chmod +x on cached Chromium binaries."""
    try:
        cache = _cache_dir()
        if not cache.exists():
            return
        for root, dirs, files in os.walk(str(cache)):
            for d in dirs:
                try:
                    os.chmod(os.path.join(root, d), 0o755)
                except Exception:
                    pass
            for f in files:
                fp = os.path.join(root, f)
                try:
                    st = os.stat(fp)
                    os.chmod(fp, st.st_mode | 0o111)
                except Exception:
                    pass
    except Exception:
        pass


def _install_browser_sync():
    """Run `playwright install chromium` with cache dir set."""
    global _install_done
    if _install_done or _browser_cached():
        _install_done = True
        return
    cache = _cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(cache)
    try:
        r = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            env=env, capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            raise RuntimeError(
                f"playwright install failed: {r.stderr[-300:]}"
            )
        # Part 63.1: ensure Chromium binaries are executable. HF Spaces
        # sometimes extracts them without +x — first launch works, then
        # EACCES on cold restart.
        try:
            for root, dirs, files in os.walk(str(cache)):
                for d in dirs:
                    try:
                        os.chmod(os.path.join(root, d), 0o755)
                    except Exception:
                        pass
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        st = os.stat(fp)
                        os.chmod(fp, st.st_mode | 0o111)
                    except Exception:
                        pass
        except Exception:
            pass
        _install_done = True
    except subprocess.TimeoutExpired:
        raise RuntimeError("playwright install timed out (10 min)")


async def _ensure_installed():
    if _install_done or _browser_cached():
        return
    # Run install in a thread so we don't block the loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _install_browser_sync)


def _browser_alive(b) -> bool:
    """True if the browser process is still connected."""
    if b is None:
        return False
    try:
        return bool(b.is_connected())
    except Exception:
        return False


async def get_browser():
    """Return shared Chromium. Lazy-starts Playwright on first call.
    Re-launches if the singleton has died (TargetClosedError protection)."""
    global _browser, _playwright
    if _browser_alive(_browser):
        return _browser
    async with _lock:
        if _browser_alive(_browser):
            return _browser
        # Singleton is dead (or was never set) — reset and relaunch
        _browser = None
        await _ensure_installed()
        # Ensure Playwright sees the cached browser
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_cache_dir())
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()

        args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--no-zygote",
            "--single-process",
        ]

        try:
            _browser = await _playwright.chromium.launch(
                headless=True, args=args,
            )
            return _browser
        except Exception as first_err:
            # Part 63.2: on EACCES / permission error, try chmod-only first
            # (instant). Only wipe + reinstall if that still fails.
            msg = str(first_err)
            is_perm = ("EACCES" in msg or "permission" in msg.lower()
                       or "executable" in msg.lower())
            if not is_perm:
                # Non-permission error: reset singleton so next call retries
                _browser = None
                raise
            print("[browser] launch failed with permission error, chmod retry")
            _chmod_cache()
            try:
                _browser = await _playwright.chromium.launch(
                    headless=True, args=args,
                )
                return _browser
            except Exception as second_err:
                print(f"[browser] chmod retry failed: {second_err}")
                # Last resort: wipe + reinstall
                try:
                    import shutil
                    shutil.rmtree(str(_cache_dir()), ignore_errors=True)
                except Exception:
                    pass
                global _install_done
                _install_done = False
                await _ensure_installed()
                _chmod_cache()
                _browser = await _playwright.chromium.launch(
                    headless=True, args=args,
                )
                return _browser

        # unreachable, but silence linters
        raise RuntimeError("browser launch exhausted retries")


async def new_context():
    """Return a fresh BrowserContext (isolated cookies/storage)."""
    b = await get_browser()
    ctx = await b.new_context(
        user_agent=_DEFAULT_UA,
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
    )
    ctx.set_default_timeout(_NAV_TIMEOUT_MS)
    return ctx


# ── SSRF guard (reuse api_call's logic) ────────────────────────
_allow_re = re.compile(r"\s*")


def validate_url(url: str) -> str:
    """Return None if URL is allowed, else error message."""
    try:
        from .api_call import _check_url
        return _check_url(url)
    except Exception:
        # Fallback: minimal check
        if not url or not url.startswith(("http://", "https://")):
            return "url must be http(s)"
        return None
