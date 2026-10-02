#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Idempotent migration runner for Neon Postgres."""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


async def run_migrations():
    load_dotenv()
    url = os.getenv("NEON_DATABASE_URL")
    if not url:
        print("ERROR: NEON_DATABASE_URL not set")
        return 1

    print("-> Connecting to Neon...")
    conn = await asyncpg.connect(url, statement_cache_size=0)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     TEXT PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        applied = {
            r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")
        }
        print(f"-> Already applied: {len(applied)} migration(s)")

        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not files:
            print("-> No migration files found")
            return 0

        for f in files:
            version = f.stem
            if version in applied:
                print(f"  [skip] {version} (already applied)")
                continue

            print(f"  -> Applying {version}...")
            sql = f.read_text()
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)", version
                )
            print(f"  [ok] {version} applied")

        print("[done] All migrations complete")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(run_migrations()))
