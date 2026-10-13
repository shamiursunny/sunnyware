-- SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
-- SPDX-License-Identifier: AGPL-3.0-only
-- Part 76: email send log

CREATE TABLE IF NOT EXISTS email_send_log (
  id BIGSERIAL PRIMARY KEY,
  to_emails TEXT NOT NULL,
  cc_emails TEXT,
  bcc_emails TEXT,
  subject TEXT NOT NULL,
  body_preview TEXT,
  attachments TEXT,
  ok BOOLEAN NOT NULL,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_email_send_log_ts
  ON email_send_log (created_at DESC);
