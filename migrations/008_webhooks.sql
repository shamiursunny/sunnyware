-- SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
-- SPDX-License-Identifier: AGPL-3.0-only
-- Part 83: webhook receiver

CREATE TABLE IF NOT EXISTS webhook_endpoints (
  token TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  trigger_prompt TEXT DEFAULT '',
  notify_email TEXT DEFAULT '',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  hit_count BIGINT NOT NULL DEFAULT 0,
  last_hit_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS webhook_events (
  id BIGSERIAL PRIMARY KEY,
  endpoint_token TEXT NOT NULL REFERENCES webhook_endpoints(token) ON DELETE CASCADE,
  source_ip TEXT,
  headers JSONB,
  payload JSONB,
  processed BOOLEAN NOT NULL DEFAULT FALSE,
  response_preview TEXT,
  error TEXT,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_webhook_events_token_ts
  ON webhook_events (endpoint_token, received_at DESC);
