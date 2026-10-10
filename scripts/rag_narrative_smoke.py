#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Narrative smoke test — verifies /api/rag/query with_narrative=true.

Requires LLM_BASE_URL / LLM_API_KEY / LLM_MODEL to be configured and reachable.
If the LLM is unreachable, verifies graceful fallback to the stub report.
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
    async with httpx.AsyncClient(
        transport=transport, base_url="http://rag-narr", timeout=180.0
    ) as c:
        # Fresh state
        await c.post("/api/rag/reset")

        # Upload
        r = await c.post(
            "/api/rag/upload",
            files={"file": ("q3_budget.csv", CSV, "text/csv")},
        )
        assert r.status_code == 200, r.text
        up = r.json()
        print("[upload] chunks_added:", up["chunks_added"])

        # Query with narrative
        r = await c.post(
            "/api/rag/query",
            json={
                "query": "Summarize the Marketing and Sales variances.",
                "k": 3,
                "with_narrative": True,
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()

        if d.get("narrative"):
            print()
            print("[narrative] OK  model:", d.get("narrative_model"))
            print("            latency_ms:", d.get("narrative_latency_ms"))
            print("            length:", len(d["narrative"]), "chars")
            print("            --- preview (first 400 chars) ---")
            print(d["narrative"][:400])
            print("            --------------------------------")
            assert len(d["narrative"]) > 50, "narrative too short"
            print()
            print("NARRATIVE PATH: PASS (live LLM)")
        elif d.get("narrative_fallback"):
            print()
            print("[narrative] LLM unreachable -> graceful fallback")
            print("            error:", d.get("narrative_error"))
            print("            latency_ms:", d.get("narrative_latency_ms"))
            print("            --- fallback preview ---")
            print(d["narrative_fallback"][:300])
            print("            -----------------------")
            assert len(d["narrative_fallback"]) > 30
            print()
            print("FALLBACK PATH: PASS (LLM will activate when reachable)")
        else:
            print()
            print("[FAIL] neither narrative nor fallback in response:")
            print(d)
            sys.exit(1)

        # Cleanup
        await c.post("/api/rag/reset")


if __name__ == "__main__":
    asyncio.run(main())
