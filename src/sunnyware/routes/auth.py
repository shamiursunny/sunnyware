# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Auth status endpoint — always public (never requires API key)."""

from fastapi import APIRouter

from .. import auth


router = APIRouter()


@router.get("/api/auth/status")
async def auth_status():
    """Inspect auth + rate-limit configuration (public endpoint)."""
    return auth.status()
