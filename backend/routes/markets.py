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
from calibration import compute_calibration
from conviction import find_best_opportunities, summarise_signals

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
    """Return all Glimpse market batches, falling back to demo batch if API key is not configured."""
    api_key = os.getenv("GLIMPSE_API_KEY", "")
    if api_key and api_key != "paste_your_key_here":
        try:
            async with _get_client() as client:
                batches = await client.get_batches()
            return {"success": True, "batches": batches, "demo_mode": False}
        except Exception as exc:
            logger.warning("Failed to fetch live batches from Glimpse: %s", exc)

    demo_batches = [
        {
            "batch_id": "demo-batch-btc",
            "main_topic_title": "Bitcoin (BTC) Price Markets — Demo",
            "topic_type": "btc",
            "status": "active",
            "is_demo": True,
        }
    ]
    return {"success": True, "batches": demo_batches, "demo_mode": True}


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


# ---------------------------------------------------------------------------
# Conviction signals
# ---------------------------------------------------------------------------

@router.get("/signals")
async def get_conviction_signals(
    batch_id: str = Query(..., description="Batch UUID"),
    topic_type: Optional[str] = Query("btc", description="Topic type filter (default: btc)"),
    min_score: float = Query(0.05, ge=0.0, le=1.0, description="Minimum conviction score"),
    top_n: int = Query(20, ge=1, le=100, description="Max number of signals to return"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    """
    Score live active markets against historical calibration and return
    ranked conviction signals — the heart of Layer 2.

    Requires resolved markets to have been synced (/api/markets/sync) so
    that calibration data is available.
    """
    # 1. Load calibration from cache or compute fresh
    cached_cal = db.get_latest_calibration(batch_id, topic_type or "btc")
    if not cached_cal:
        # Try computing on the fly from cached markets
        markets = db.get_resolved_markets(batch_id, topic_type=topic_type)
        if not markets:
            return {
                "success": False,
                "message": "No resolved markets cached. Run /api/markets/sync first.",
                "signals": [],
                "summary": {},
            }
        cached_cal = compute_calibration(markets)

    DEMO_ACTIVE_MARKETS = [
        {
            "topic_id": 90001,
            "title": "BTC Spot > $98,500 at 00:00 UTC",
            "category": "Crypto",
            "batch_id": "demo-batch-btc",
            "outcomes": [
                {"option_id": 1, "option_title": "Yes (Above $98.5k)", "yes_price": 0.35},
                {"option_id": 2, "option_title": "No (Below $98.5k)", "yes_price": 0.65},
            ],
        },
        {
            "topic_id": 90002,
            "title": "BTC Range: $95,000 to $96,500 at Close",
            "category": "Crypto",
            "batch_id": "demo-batch-btc",
            "outcomes": [
                {"option_id": 1, "option_title": "In Range", "yes_price": 0.54},
                {"option_id": 2, "option_title": "Out of Range", "yes_price": 0.46},
            ],
        },
        {
            "topic_id": 90003,
            "title": "BTC Above $102,000 End of Week",
            "category": "Crypto",
            "batch_id": "demo-batch-btc",
            "outcomes": [
                {"option_id": 1, "option_title": "Above $102k", "yes_price": 0.78},
                {"option_id": 2, "option_title": "Below $102k", "yes_price": 0.22},
            ],
        },
        {
            "topic_id": 90004,
            "title": "BTC Retraces Below $92,000",
            "category": "Crypto",
            "batch_id": "demo-batch-btc",
            "outcomes": [
                {"option_id": 1, "option_title": "Retraces Below", "yes_price": 0.14},
                {"option_id": 2, "option_title": "Holds Above", "yes_price": 0.86},
            ],
        },
    ]

    api_key = os.getenv("GLIMPSE_API_KEY", "")
    is_demo = batch_id.startswith("demo-") or not api_key or api_key == "paste_your_key_here"

    if is_demo:
        enriched_markets = DEMO_ACTIVE_MARKETS
    else:
        # 2. Fetch live active markets
        try:
            async with _get_client() as client:
                active_data = await client.get_active_markets_v2(
                    batch_id, page=page, page_size=page_size
                )
        except GlimpseAPIError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        active_markets = active_data.get("markets", []) or active_data.get("data", [])

        if not active_markets:
            return {
                "success": True,
                "message": "No active markets found in this batch.",
                "signals": [],
                "summary": {},
            }

        # 3. For each active market, fetch full quotes to get per-outcome yes_price
        enriched_markets = []
        async with _get_client() as client:
            for market in active_markets:
                tid = market.get("topic_id") or market.get("id")
                if not tid:
                    continue
                try:
                    quotes = await client.get_market_quotes(tid)
                    outcomes = quotes.get("outcomes") or quotes.get("options") or []
                    enriched_markets.append({
                        **market,
                        "outcomes": outcomes,
                    })
                except GlimpseAPIError:
                    pass

    # 4. Score all enriched markets
    signals = find_best_opportunities(
        active_markets=enriched_markets,
        calibration_data=cached_cal,
        min_score=min_score,
        top_n=top_n,
    )
    summary = summarise_signals(signals)

    return {
        "success": True,
        "batch_id": batch_id,
        "topic_type": topic_type,
        "active_markets_scanned": len(enriched_markets),
        "signals": signals,
        "summary": summary,
    }
