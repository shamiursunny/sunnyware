-- SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
-- SPDX-License-Identifier: AGPL-3.0-only
-- Part 84: SQL sandbox (ad-hoc SQL for agent)

CREATE TABLE IF NOT EXISTS sql_sandboxes (
  name TEXT PRIMARY KEY,
  schema_name TEXT NOT NULL,
  description TEXT DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_used_at TIMESTAMPTZ,
  query_count BIGINT NOT NULL DEFAULT 0
);
