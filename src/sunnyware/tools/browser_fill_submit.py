# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Browser form fill + submit tool (Part 63)."""

import re


class BrowserFillSubmitTool:
    name = "browser_fill_submit"
    description = (
        "Open a URL, fill one or more form fields (either CSS selectors or human labels), "
        "then submit by clicking a button selector or pressing Enter. "
        "Returns the resulting page. Use for contact forms, search forms, login/register forms, "        
        "comment boxes, or chat inputs."
    )
    parameters = {
        "url": {"type": "string", "required": True, "description": "Form URL"},
        "fields": {
            "type": "object",
            "required": False,
            "description": "Map of field label (e.g., 'Name', 'Email') or CSS selector -> value to fill",
        },
        "chat_message": {
            "type": "string",
            "required": False,
            "description": "If provided, find a main text input (textarea/chat box) and send this message",     
        },
        "submit_selector": {
            "type": "string",
            "required": False,
            "description": "CSS selector of submit button (else auto-detect)",
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
        chat_message = (args.get("chat_message") or "").strip()
        if not isinstance(fields, dict):
            return {"error": "fields must be an object"}
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
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            if chat_message:
                input_selector = await page.evaluate('''() => {
                    const candidates = [
                        'textarea[placeholder*="message" i]',
                        'textarea[placeholder*="chat" i]',
                        'input[placeholder*="message" i]',
                        'input[placeholder*="chat" i]',
                        'textarea:not([readonly])',
                        'input[type="text"]:not([readonly])',
                        'div[contenteditable="true"]'
                    ];
                    for (const sel of candidates) {
                        const el = document.querySelector(sel);
                        if (el && el.offsetParent !== null) return sel;
                    }
                    return null;
                }''')
                if not input_selector:
                    return {"error": "could not find a chat input box"}
                await page.fill(input_selector, chat_message, timeout=8000)
                send_btn = page.locator('button:has-text("Send"), button[aria-label*="send" i], button[type="submit"]').first
                if await send_btn.count() > 0:
                    await send_btn.click(timeout=5000)
                else:
                    await page.keyboard.press("Enter")
            else:
                if not fields:
                    return {"error": "either fields or chat_message is required"}
                for key, val in fields.items():
                    selector = await self._resolve_selector(page, str(key))
                    if not selector:
                        return {"error": f"could not resolve selector for '{key}'"}
                    await page.fill(selector, str(val), timeout=8000)

                if submit_sel:
                    btn = page.locator(submit_sel).first
                    if await btn.count() == 0:
                        return {"error": f"submit selector not found: {submit_sel}"}
                    await btn.click(timeout=8000)
                else:
                    auto_btn = await page.evaluate('''() => {
                        const std = ['button[type="submit"]', 'input[type="submit"]'];
                        for (const sel of std) {
                            try {
                                const el = document.querySelector(sel);
                                if (el && el.offsetParent !== null) {
                                    el.setAttribute('data-sunny-submit', '1');
                                    return '[data-sunny-submit="1"]';
                                }
                            } catch (e) {}
                        }
                        const texts = ['send', 'submit', 'login', 'sign in', 'register', 'comment', 'post'];    
                        const buttons = document.querySelectorAll('button, input[type="submit"], a[role="button"]');
                        for (let i = 0; i < buttons.length; i++) {
                            const btn = buttons[i];
                            if (btn.offsetParent === null) continue;
                            const label = (btn.textContent || btn.value || '').toLowerCase().trim();
                            if (texts.some(t => label.includes(t))) {
                                btn.setAttribute('data-sunny-submit', '1');
                                return '[data-sunny-submit="1"]';
                            }
                        }
                        return null;
                    }''')
                    if auto_btn:
                        await page.click(auto_btn, timeout=8000)
                    else:
                        await page.keyboard.press("Enter")

            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            if wait_ms:
                await page.wait_for_timeout(wait_ms)
            html = await page.content()
            title = await page.title()
            final_url = page.url
        except Exception as e:
            if fields and not chat_message:
                return self._fallback_submit(url, fields, e)
            return {"error": f"{type(e).__name__}: {e}"}
        finally:
            if ctx:
                try: await ctx.close()
                except Exception: pass

        return {
            "status": "success",
            "message": f"Form submitted successfully. Final page title: {title}",
            "start_url": url,
            "final_url": final_url,
            "title": title,
            "fields_filled": len(fields) if fields else 1,
            "html": html[:max_chars],
            "html_chars": len(html),
            "truncated": len(html) > max_chars,
        }

    async def _resolve_selector(self, page, key: str) -> str | None:
        key = key.strip()
        if any(c in key for c in '[#.]') or key in ('input', 'textarea', 'button', 'select'):
            try:
                if await page.locator(key).count() > 0:
                    return key
            except Exception:
                pass

        candidates = [
            f'input[name="{key}" i]',
            f'input[placeholder*="{key}" i]',
            f'textarea[name="{key}" i]',
            f'textarea[placeholder*="{key}" i]',
            f'label:has-text("{key}") + input',
            f'label:has-text("{key}") + textarea',
            f'input[aria-label*="{key}" i]',
            f'textarea[aria-label*="{key}" i]',
        ]
        for sel in candidates:
            try:
                if await page.locator(sel).count() > 0:
                    return sel
            except Exception:
                continue
                
        sel = await page.evaluate('''(label) => {
            const inputs = document.querySelectorAll('input, textarea, select');
            for (const el of inputs) {
                const id = el.id;
                if (id) {
                    const lbl = document.querySelector(`label[for="${id}"]`);
                    if (lbl && lbl.textContent.toLowerCase().includes(label.toLowerCase())) return `#${id}`;    
                }
                if (el.name && el.name.toLowerCase().includes(label.toLowerCase())) {
                    return el.tagName.toLowerCase() + `[name="${el.name}"]`;
                }
                if (el.placeholder && el.placeholder.toLowerCase().includes(label.toLowerCase())) {
                    return el.tagName.toLowerCase() + (el.name ? `[name="${el.name}"]` : '');
                }
            }
            return null;
        }''', key)
        if sel:
            return sel
        return None

    def _fallback_submit(self, url: str, fields: dict, original_error: Exception) -> dict:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            return {"error": f"playwright failed: {type(original_error).__name__}; fallback GET: {e}"}

        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        if not form:
            return {"error": f"playwright failed: {type(original_error).__name__}; fallback: no <form> found"}  

        action = form.get("action") or url
        if not action.startswith(("http://", "https://")):
            action = urljoin(url, action)
        method = (form.get("method") or "GET").upper()

        data = {}
        available = []
        for inp in form.find_all(["input", "textarea"]):
            name = inp.get("name")
            if not name:
                continue
            available.append(name)
            inp_id = inp.get("id") or ""
            placeholder = (inp.get("placeholder") or "").lower()
            label_text = ""
            if inp_id:
                lbl = soup.find("label", attrs={"for": inp_id})
                if lbl:
                    label_text = lbl.get_text(strip=True).lower()
            for field_key, value in fields.items():
                fk = field_key.lower()
                if fk in name.lower() or fk in placeholder or fk in label_text:
                    data[name] = value
                    break

        if not data:
            return {"error": f"playwright failed: {type(original_error).__name__}; fallback: could not map fields. available: {available}"}

        try:
            if method == "POST":
                final = session.post(action, data=data, timeout=15)
            else:
                final = session.get(action, params=data, timeout=15)
        except Exception as e:
            return {"error": f"playwright failed: {type(original_error).__name__}; fallback POST: {e}"}

        return {
            "status": "success",
            "message": "Form submitted via requests fallback.",
            "mode": "requests-fallback",
            "start_url": url,
            "final_url": final.url,
            "status_code": final.status_code,
            "fields_mapped": data,
            "html": final.text[:60000],
            "html_chars": len(final.text),
            "truncated": len(final.text) > 60000,
            "note": f"playwright failed: {type(original_error).__name__}",
        }
