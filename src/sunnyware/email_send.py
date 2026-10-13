# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Email send core (Part 76, Resend API).

HF Spaces blocks outbound SMTP (ports 25/465/587). We use Resend's
HTTPS API (port 443) instead. Same function signatures as the SMTP
version, so tools + kpi_watch wiring are unchanged.

Env vars:
  RESEND_API_KEY        (required)    e.g. re_xxxxxxxx
  RESEND_FROM           (optional)    default: onboarding@resend.dev
  RESEND_FROM_NAME      (optional)    default: Sunnyware
"""
import base64
import os
from pathlib import Path

try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    _HAS_HTTPX = False

from . import state as app_state


_RESEND_URL = "https://api.resend.com/emails"
_MAX_TO = 10
_MAX_ATTACH_MB = 2
_MAX_ATTACH_BYTES = _MAX_ATTACH_MB * 1024 * 1024
_ATTACH_EXTS = {".pdf", ".csv", ".txt", ".md", ".xlsx", ".png", ".jpg", ".json"}
_TIMEOUT = 20.0


def _cfg():
    return {
        "api_key": os.getenv("RESEND_API_KEY", "").strip(),
        "from_addr": os.getenv("RESEND_FROM", "onboarding@resend.dev").strip(),
        "from_name": os.getenv("RESEND_FROM_NAME", "Sunnyware").strip(),
    }


def is_configured() -> bool:
    return bool(_cfg()["api_key"])


def config_summary() -> dict:
    c = _cfg()
    return {
        "configured": is_configured(),
        "provider": "resend",
        "from": c["from_addr"],
        "from_name": c["from_name"],
        "api_key_set": bool(c["api_key"]),
        "note": (
            "Resend sends only to verified emails unless a domain is "
            "verified. Free tier: 3000/month, 100/day."
        ),
    }


def _workspace_root() -> Path:
    p = os.getenv("SUNNYWARE_WORKSPACE") or os.getenv("WORKSPACE_PATH")
    if p:
        return Path(p).resolve()
    return Path("/data/workspace").resolve()


def _norm_emails(v) -> list:
    if not v:
        return []
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    out = []
    for e in v:
        s = str(e).strip()
        if s and "@" in s and len(s) < 200:
            out.append(s)
    return out[:_MAX_TO]


async def _log_send(to, cc, bcc, subject, body_preview, attach_names, ok, error):
    pool = app_state.get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO email_send_log
                   (to_emails, cc_emails, bcc_emails, subject, body_preview,
                    attachments, ok, error)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                ",".join(to), ",".join(cc) if cc else None,
                ",".join(bcc) if bcc else None,
                subject, (body_preview or "")[:500],
                ",".join(attach_names) if attach_names else None,
                bool(ok), (error or "")[:500],
            )
    except Exception:
        pass


async def send_email(to, subject, body, html=False, cc=None, bcc=None,
                     attachments=None) -> dict:
    if not _HAS_HTTPX:
        return {"error": "httpx not available"}

    if not is_configured():
        return {
            "error": "Resend API not configured",
            "setup_hint": (
                "Set RESEND_API_KEY on the HF Space (Settings -> Variables "
                "and secrets). Sign up at https://resend.com/signup to get "
                "a free API key. Optional: RESEND_FROM (verified sender), "
                "RESEND_FROM_NAME."
            ),
        }

    to_list = _norm_emails(to)
    cc_list = _norm_emails(cc)
    bcc_list = _norm_emails(bcc)
    if not to_list:
        return {"error": "to must contain at least one valid email"}

    subject = (subject or "").strip()
    if not subject:
        return {"error": "subject is required"}
    if len(subject) > 500:
        return {"error": "subject too long (max 500 chars)"}

    body = body or ""
    if not body.strip():
        return {"error": "body is required"}
    if len(body) > 500_000:
        return {"error": "body too large (max 500 KB)"}

    c = _cfg()
    from_field = c["from_name"] + " <" + c["from_addr"] + ">" if c["from_name"] else c["from_addr"]

    payload = {
        "from": from_field,
        "to": to_list,
        "subject": subject,
    }
    if cc_list:
        payload["cc"] = cc_list
    if bcc_list:
        payload["bcc"] = bcc_list
    if html:
        payload["html"] = body
    else:
        payload["text"] = body

    # Attachments (base64)
    attach_names = []
    if attachments:
        if not isinstance(attachments, list):
            attachments = [attachments]
        att_list = []
        total = 0
        root = _workspace_root()
        for fname in attachments[:5]:
            fname = str(fname).strip()
            if not fname:
                continue
            candidate = (root / fname).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                return {"error": "attachment must live in workspace: " + fname}
            if not candidate.exists() or not candidate.is_file():
                return {"error": "attachment not found: " + fname}
            if candidate.suffix.lower() not in _ATTACH_EXTS:
                return {"error": "attachment type not allowed: " + candidate.suffix}
            data = candidate.read_bytes()
            total += len(data)
            if total > _MAX_ATTACH_BYTES:
                return {"error": "total attachment size exceeds " + str(_MAX_ATTACH_MB) + " MB"}
            att_list.append({
                "filename": candidate.name,
                "content": base64.b64encode(data).decode("ascii"),
            })
            attach_names.append(candidate.name)
        if att_list:
            payload["attachments"] = att_list

    # Send via Resend
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                _RESEND_URL,
                json=payload,
                headers={
                    "Authorization": "Bearer " + c["api_key"],
                    "Content-Type": "application/json",
                },
            )
    except httpx.TimeoutException:
        await _log_send(to_list, cc_list, bcc_list, subject,
                        body[:500], attach_names, False, "timeout")
        return {"error": "Resend API timeout after " + str(_TIMEOUT) + "s"}
    except Exception as e:
        err = type(e).__name__ + ": " + str(e)[:200]
        await _log_send(to_list, cc_list, bcc_list, subject,
                        body[:500], attach_names, False, err)
        return {"error": err}

    ok = 200 <= r.status_code < 300
    body_snip = r.text[:500] if not ok else ""
    message_id = None
    if ok:
        try:
            message_id = r.json().get("id")
        except Exception:
            pass

    await _log_send(to_list, cc_list, bcc_list, subject,
                    body[:500], attach_names, ok,
                    None if ok else "HTTP " + str(r.status_code) + ": " + body_snip)

    if not ok:
        return {
            "error": "Resend API error: HTTP " + str(r.status_code),
            "details": body_snip,
        }

    return {
        "ok": True,
        "message_id": message_id,
        "to": to_list,
        "cc": cc_list,
        "bcc_count": len(bcc_list),
        "subject": subject,
        "attachments": attach_names,
        "chars_sent": len(body),
        "provider": "resend",
    }


async def list_sent(limit: int = 20) -> dict:
    pool = app_state.get_pool()
    if pool is None:
        return {"error": "database unavailable"}
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT to_emails, cc_emails, subject, body_preview,
                          attachments, ok, error, created_at
                   FROM email_send_log
                   ORDER BY created_at DESC LIMIT $1""",
                limit,
            )
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)}

    items = [{
        "to": r["to_emails"],
        "cc": r["cc_emails"],
        "subject": r["subject"],
        "body_preview": r["body_preview"],
        "attachments": r["attachments"],
        "ok": bool(r["ok"]),
        "error": r["error"],
        "sent_at": r["created_at"].isoformat() if r["created_at"] else None,
    } for r in rows]
    return {"count": len(items), "items": items}
