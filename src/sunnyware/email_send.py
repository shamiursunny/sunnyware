# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Email send core (Part 76).

Gmail SMTP via smtplib. Degrades gracefully when env vars missing.
Logs every attempt to Neon email_send_log.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional
from . import state as app_state


_MAX_TO = 10
_MAX_ATTACH_MB = 2
_MAX_ATTACH_BYTES = _MAX_ATTACH_MB * 1024 * 1024
_ATTACH_EXTS = {".pdf", ".csv", ".txt", ".md", ".xlsx", ".png", ".jpg", ".json"}


def _cfg():
    return {
        "host": os.getenv("SUNNYWARE_SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SUNNYWARE_SMTP_PORT", "587")),
        "user": os.getenv("SUNNYWARE_SMTP_USER", ""),
        "password": os.getenv("SUNNYWARE_SMTP_PASS", ""),
        "from_addr": os.getenv("SUNNYWARE_EMAIL_FROM", os.getenv("SUNNYWARE_SMTP_USER", "")),
        "from_name": os.getenv("SUNNYWARE_EMAIL_FROM_NAME", "Sunnyware"),
    }


def is_configured() -> bool:
    c = _cfg()
    return bool(c["user"] and c["password"] and c["from_addr"])


def config_summary() -> dict:
    c = _cfg()
    return {
        "configured": is_configured(),
        "host": c["host"],
        "port": c["port"],
        "from": c["from_addr"] if c["from_addr"] else None,
        "from_name": c["from_name"],
        "user_set": bool(c["user"]),
        "password_set": bool(c["password"]),
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


async def send_email(
    to,
    subject: str,
    body: str,
    html: bool = False,
    cc=None,
    bcc=None,
    attachments=None,
) -> dict:
    """Send an email. Returns {ok, message_id} or {error, setup_hint}."""
    if not is_configured():
        return {
            "error": "SMTP not configured",
            "setup_hint": (
                "Set SUNNYWARE_SMTP_USER, SUNNYWARE_SMTP_PASS, "
                "SUNNYWARE_EMAIL_FROM on the HF Space (Settings -> "
                "Variables and secrets). For Gmail, generate a 16-char "
                "app password at myaccount.google.com/apppasswords."
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

    # Build message
    c = _cfg()
    msg = MIMEMultipart()
    msg["From"] = "{} <{}>".format(c["from_name"], c["from_addr"])
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject

    if html:
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        msg.attach(MIMEText(body, "plain", "utf-8"))

    # Attachments from workspace
    attach_names = []
    if attachments:
        if not isinstance(attachments, list):
            attachments = [attachments]
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
            part = MIMEBase("application", "octet-stream")
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition",
                            "attachment; filename=\"" + candidate.name + "\"")
            msg.attach(part)
            attach_names.append(candidate.name)

    # Send
    try:
        with smtplib.SMTP(c["host"], c["port"], timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(c["user"], c["password"])
            result = server.send_message(
                msg, from_addr=c["from_addr"],
                to_addrs=to_list + cc_list + bcc_list,
            )
        errs = {k: v for k, v in (result or {}).items() if v}
        ok = not errs
        err_msg = None if ok else str(errs)[:500]
    except smtplib.SMTPAuthenticationError as e:
        ok = False
        err_msg = "SMTP auth failed: " + str(e)[:200]
    except Exception as e:
        ok = False
        err_msg = type(e).__name__ + ": " + str(e)[:200]

    await _log_send(to_list, cc_list, bcc_list, subject,
                    body[:500], attach_names, ok, err_msg)

    if not ok:
        return {"error": err_msg or "send failed"}

    return {
        "ok": True,
        "to": to_list,
        "cc": cc_list,
        "bcc_count": len(bcc_list),
        "subject": subject,
        "attachments": attach_names,
        "chars_sent": len(body),
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
