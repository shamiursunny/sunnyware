#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""End-to-end RAG smoke test — in-process ASGI, no server subprocess needed.

Flow:
  1. GET  /api/rag/status       -> empty store
  2. POST /api/rag/upload       -> CSV file (3 rows)
  3. POST /api/rag/query        -> semantic search
  4. GET  /api/rag/status       -> count > 0
  5. POST /api/rag/reset        -> wipe store
  6. GET  /api/rag/status       -> count == 0
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import httpx
from sunnyware.main import app


CSV = b"""department,account,actual,budget,variance
Marketing,Ad Spend,12000,10000,2000
Sales,Commission,54000,50000,4000
Engineering,Cloud Infra,8000,7500,500
"""


async def main():
    transport = httpx.ASGITransport(app=app)
    failures = []

    async with httpx.AsyncClient(
        transport=transport, base_url="http://rag-smoke", timeout=60.0
    ) as c:

        # 1. initial status
        r = await c.get("/api/rag/status")
        print("[1] status       ", r.status_code, r.json())
        assert r.status_code == 200
        body = r.json()
        assert "count" in body and "model" in body

        # 2. reset to a clean slate (so re-runs are deterministic)
        r = await c.post("/api/rag/reset")
        print("[2] reset         ", r.status_code, r.json())
        assert r.status_code == 200

        # 3. upload CSV
        files = {"file": ("budget_q3.csv", CSV, "text/csv")}
        r = await c.post("/api/rag/upload", files=files)
        print("[3] upload        ", r.status_code, r.json())
        assert r.status_code == 200, r.text
        up = r.json()
        assert up["ok"] is True
        assert up["chunks_added"] >= 1
        assert up["extension"] == ".csv"

        # 4. query
        r = await c.post(
            "/api/rag/query",
            json={"query": "How much did Marketing spend?", "k": 2},
        )
        print("[4] query         ", r.status_code, r.json())
        assert r.status_code == 200, r.text
        q = r.json()
        assert len(q["hits"]) >= 1
        top = q["hits"][0]
        assert top["source"] == "budget_q3.csv"
        assert "Marketing" in (top["preview"] or "")
        print("    top hit     ->", top["preview"][:80])

        # 5. query with prompt
        r = await c.post(
            "/api/rag/query",
            json={"query": "Marketing variance", "k": 1, "with_prompt": True},
        )
        assert r.status_code == 200
        q2 = r.json()
        assert "prompt" in q2 and "EXECUTIVE FINANCIAL SUMMARY" in q2["prompt"]
        print("[5] prompt built  ", len(q2["prompt"]), "chars")

        # 6. status reflects count
        r = await c.get("/api/rag/status")
        s = r.json()
        print("[6] status2       ", r.status_code, {"count": s["count"]})
        assert s["count"] == up["total_count"]

        # 7. unsupported ext
        files = {"file": ("bad.exe", b"nope", "application/octet-stream")}
        r = await c.post("/api/rag/upload", files=files)
        print("[7] bad ext       ", r.status_code, r.json().get("error"))
        assert r.status_code == 400

        # 8. empty query
        r = await c.post("/api/rag/query", json={"query": ""})
        print("[8] empty query   ", r.status_code, r.json().get("error"))
        assert r.status_code == 400

        # 9. reset
        r = await c.post("/api/rag/reset")
        print("[9] reset         ", r.status_code, r.json())
        assert r.status_code == 200
        assert r.json()["count"] == 0

        # 10. final status
        r = await c.get("/api/rag/status")
        s = r.json()
        print("[10] final        ", r.status_code, {"count": s["count"]})
        assert s["count"] == 0

    print()
    if failures:
        print("FAILURES:", failures)
        sys.exit(1)
    print("ALL RAG E2E SMOKE TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
