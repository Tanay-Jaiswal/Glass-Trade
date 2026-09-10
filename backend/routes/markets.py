"""
routes/markets.py — Market data endpoints.

GET /api/batches                  — list all Glimpse batches
GET /api/markets/resolved         — return cached resolved markets
POST /api/markets/sync            — pull new resolved markets from API into SQLite
GET /api/markets/active           — live active markets with quotes
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

import database as db
from api_client import GlimpseClient, GlimpseAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/markets", tags=["markets"])

batches_router = APIRouter(prefix="/api", tags=["batches"])


def _get_client() -> GlimpseClient:
    api_key = os.getenv("GLIMPSE_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GLIMPSE_API_KEY not configured. Set it in your .env file.",
        )
    return GlimpseClient(api_key=api_key)


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------

@batches_router.get("/batches")
async def list_batches():
    """Return all Glimpse market batches."""
    try:
        async with _get_client() as client:
            batches = await client.get_batches()
        return {"success": True, "batches": batches}
    except GlimpseAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---------------------------------------------------------------------------
# Resolved markets
# ---------------------------------------------------------------------------

@router.get("/resolved")
async def get_resolved_markets(
    batch_id: str = Query(..., description="Batch UUID"),
    topic_type: Optional[str] = Query(None, description="Filter by topic type, e.g. 'btc'"),
):
    """
    Return resolved markets from local SQLite cache.
    Call /api/markets/sync first to populate the cache.
    """
    markets = db.get_resolved_markets(batch_id, topic_type=topic_type)
    return {
        "success": True,
        "count": len(markets),
        "batch_id": batch_id,
        "topic_type": topic_type,
        "markets": markets,
    }


@router.post("/sync")
async def sync_resolved_markets(
    batch_id: str = Query(..., description="Batch UUID"),
    topic_type: Optional[str] = Query("btc", description="Topic type filter (default: btc)"),
    background_tasks: BackgroundTasks = None,
):
    """
    Pull resolved markets from the Glimpse API and cache them in SQLite.
    This can take 20-60s for large batches; progress is logged server-side.
    Returns immediately with a status message.
    """
    async def _do_sync():
        try:
            async with _get_client() as client:
                total_fetched = 0

                def progress(fetched, total):
                    nonlocal total_fetched
                    total_fetched = fetched
                    logger.info("Sync progress: %d / %d markets fetched", fetched, total)

                markets = await client.get_all_resolved_markets(
                    batch_id,
                    topic_type_filter=topic_type,
                    progress_callback=progress,
                )

            inserted = db.upsert_resolved_markets(markets)
            cached = db.count_cached_markets(batch_id, topic_type)
            logger.info(
                "Sync complete: %d new markets inserted, %d total cached",
                inserted, cached,
            )
        except GlimpseAPIError as exc:
            logger.error("Sync failed: %s", exc)
        except Exception as exc:
            logger.exception("Unexpected sync error: %s", exc)

    if background_tasks:
        background_tasks.add_task(_do_sync)
        return {
            "success": True,
            "message": "Sync started in background. Check server logs for progress.",
            "batch_id": batch_id,
            "topic_type": topic_type,
            "cached_before_sync": db.count_cached_markets(batch_id, topic_type),
        }
    else:
        # Foreground mode for direct calls
        await _do_sync()
        return {
            "success": True,
            "message": "Sync complete.",
            "cached": db.count_cached_markets(batch_id, topic_type),
        }


@router.get("/sync-status")
async def sync_status(
    batch_id: str = Query(...),
    topic_type: Optional[str] = Query(None),
):
    """Return how many markets are cached locally."""
    count = db.count_cached_markets(batch_id, topic_type)
    return {"batch_id": batch_id, "topic_type": topic_type, "cached_count": count}


# ---------------------------------------------------------------------------
# Active markets (live)
# ---------------------------------------------------------------------------

@router.get("/active")
async def get_active_markets(
    batch_id: str = Query(..., description="Batch UUID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Return currently active markets with slim quote data.
    Uses v2 paginated endpoint (public auth).
    """
    try:
        async with _get_client() as client:
            data = await client.get_active_markets_v2(batch_id, page=page, page_size=page_size)
        return {"success": True, **data}
    except GlimpseAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/quotes/{topic_id}")
async def get_market_quotes(topic_id: int):
    """Return live quotes for a single market including full per-outcome pricing."""
    try:
        async with _get_client() as client:
            data = await client.get_market_quotes(topic_id)
        return {"success": True, **data}
    except GlimpseAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
