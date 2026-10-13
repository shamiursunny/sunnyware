-- SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
-- SPDX-License-Identifier: AGPL-3.0-only
-- Part 81: dynamic schedules (agent-prompt recurring tasks)

CREATE TABLE IF NOT EXISTS dynamic_schedules (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  prompt TEXT NOT NULL,
  interval_seconds INTEGER NOT NULL,
  notify_email TEXT DEFAULT '',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  last_run_at TIMESTAMPTZ,
  last_status TEXT,
  last_result_preview TEXT,
  last_error TEXT,
  run_count BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dynamic_schedules_enabled
  ON dynamic_schedules (enabled, interval_seconds);
