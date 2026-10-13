# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Send email tool (Part 76)."""


class EmailSendTool:
    name = "email_send"
    description = (
        "Send an email via configured Gmail SMTP. Supports multiple to/cc/"
        "bcc recipients, optional HTML body, and workspace file "
        "attachments (PDF/CSV/TXT/MD/XLSX/PNG/JPG/JSON, max 2MB total). "
        "All sends are logged to Neon. Use for reports, alerts, "
        "notifications. Requires SUNNYWARE_SMTP_* env vars on the server."
    )
    parameters = {
        "to": {"type": "array", "required": True,
               "description": "List of recipient emails (max 10)"},
        "subject": {"type": "string", "required": True,
                    "description": "Email subject"},
        "body": {"type": "string", "required": True,
                 "description": "Email body (plain text unless html=true)"},
        "html": {"type": "boolean", "required": False,
                 "description": "Treat body as HTML (default false)"},
        "cc": {"type": "array", "required": False,
               "description": "CC recipients"},
        "bcc": {"type": "array", "required": False,
                "description": "BCC recipients"},
        "attachments": {"type": "array", "required": False,
                        "description": "Workspace filenames to attach (max 5, 2MB total)"},
    }

    async def run(self, args: dict) -> dict:
        from .. import email_send as _em
        return await _em.send_email(
            to=args.get("to"),
            subject=args.get("subject", ""),
            body=args.get("body", ""),
            html=bool(args.get("html", False)),
            cc=args.get("cc"),
            bcc=args.get("bcc"),
            attachments=args.get("attachments"),
        )
