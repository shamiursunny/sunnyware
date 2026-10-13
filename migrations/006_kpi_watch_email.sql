-- SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
-- SPDX-License-Identifier: AGPL-3.0-only
-- Part 76: KPI watch email notifications

ALTER TABLE kpi_watches ADD COLUMN IF NOT EXISTS notify_email TEXT DEFAULT '';
