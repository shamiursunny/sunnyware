-- SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
-- SPDX-License-Identifier: AGPL-3.0-only
-- Part 48: tool invocation audit trail (Reg AI compliance)

CREATE TABLE IF NOT EXISTS tool_invocations (
  id BIGSERIAL PRIMARY KEY,
  tool_name TEXT NOT NULL,
  args_hash TEXT,
  ok BOOLEAN NOT NULL,
  error TEXT,
  result_size INTEGER,
  latency_ms INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_name_ts
  ON tool_invocations (tool_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_ts
  ON tool_invocations (created_at DESC);
