-- SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
-- SPDX-License-Identifier: AGPL-3.0-only
-- Part 75: KPI watch tables

CREATE TABLE IF NOT EXISTS kpi_watches (
  id BIGSERIAL PRIMARY KEY,
  kpi_name TEXT NOT NULL UNIQUE,
  check_prompt TEXT NOT NULL,
  comparison TEXT NOT NULL,
  threshold_value DOUBLE PRECISION NOT NULL,
  extract_pattern TEXT,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  interval_seconds INTEGER NOT NULL DEFAULT 3600,
  last_run_at TIMESTAMPTZ,
  last_value DOUBLE PRECISION,
  last_status TEXT,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kpi_watch_events (
  id BIGSERIAL PRIMARY KEY,
  watch_id BIGINT NOT NULL REFERENCES kpi_watches(id) ON DELETE CASCADE,
  kpi_name TEXT NOT NULL,
  status TEXT NOT NULL,
  value DOUBLE PRECISION,
  threshold_value DOUBLE PRECISION,
  comparison TEXT,
  answer_preview TEXT,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kpi_watch_events_watch_id
  ON kpi_watch_events (watch_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_kpi_watch_events_status
  ON kpi_watch_events (status, created_at DESC);
