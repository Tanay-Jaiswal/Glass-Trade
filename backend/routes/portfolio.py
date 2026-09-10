"""
routes/portfolio.py — Portfolio endpoints (Layer 3 prep).

GET /api/portfolio   — consolidated portfolio snapshot
GET /api/portfolio/pnl  — P&L stats
"""

import logging
import os

from fastapi import APIRouter, HTTPException

from api_client import GlimpseClient, GlimpseAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _get_client() -> GlimpseClient:
    api_key = os.getenv("GLIMPSE_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GLIMPSE_API_KEY not configured.",
        )
    return GlimpseClient(api_key=api_key)


@router.get("")
async def get_portfolio():
    """Return the authenticated user's current portfolio snapshot."""
    try:
        async with _get_client() as client:
            data = await client.get_portfolio()
        return {"success": True, "portfolio": data}
    except GlimpseAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/consolidated")
async def get_consolidated_portfolio():
    """Return consolidated active positions."""
    try:
        async with _get_client() as client:
            data = await client.get_consolidated_portfolio()
        return {"success": True, "portfolio": data}
    except GlimpseAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/pnl")
async def get_pnl_stats():
    """Return aggregate P&L statistics."""
    try:
        async with _get_client() as client:
            data = await client.get_pnl_stats()
        return {"success": True, "pnl": data}
    except GlimpseAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
