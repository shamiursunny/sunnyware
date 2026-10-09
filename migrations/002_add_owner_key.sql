-- SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
-- SPDX-License-Identifier: AGPL-3.0-only
-- Part 24: per-tenant session isolation

ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner_key TEXT NOT NULL DEFAULT '';
ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_session_key_key;
DROP INDEX IF EXISTS sessions_session_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_owner_key_unique
  ON sessions (session_key, owner_key);
CREATE INDEX IF NOT EXISTS idx_sessions_owner
  ON sessions (owner_key);
