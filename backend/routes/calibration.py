"""
routes/calibration.py — Calibration computation endpoints.

GET /api/calibration/compute   — compute calibration from cached resolved markets
GET /api/calibration/summary   — quick stats without full bucket data
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import database as db
import calibration as cal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/calibration", tags=["calibration"])


@router.get("/compute")
async def compute_calibration(
    batch_id: str = Query(..., description="Batch UUID"),
    topic_type: Optional[str] = Query("btc", description="Topic type filter"),
    n_buckets: int = Query(10, ge=2, le=20, description="Number of probability buckets"),
    use_cache: bool = Query(True, description="Return cached result if available"),
):
    """
    Compute the calibration diagram and Brier score for resolved markets.

    Uses markets already cached in SQLite (run /api/markets/sync first).
    Returns bucket data suitable for rendering a reliability diagram.
    """
    # Try cache
    if use_cache:
        cached = db.get_latest_calibration(batch_id, topic_type or "all")
        if cached:
            return {"success": True, "from_cache": True, **cached}

    markets = db.get_resolved_markets(batch_id, topic_type=topic_type)
    if not markets:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No resolved markets found for batch_id={batch_id}, "
                f"topic_type={topic_type}. "
                "Run POST /api/markets/sync?batch_id=<id>&topic_type=btc first."
            ),
        )

    result = cal.compute_calibration(markets)
    result["batch_id"] = batch_id
    result["topic_type"] = topic_type
    result["n_buckets"] = n_buckets

    # Re-bucket with requested n_buckets if different from default
    if n_buckets != 10:
        from calibration import bucket_markets
        enriched = [m for m in markets if m.get("implied_prob") is not None]
        result["buckets"] = bucket_markets(enriched, n_buckets=n_buckets)

    # Cache the result
    db.save_calibration(batch_id, topic_type or "all", result)

    return {"success": True, "from_cache": False, **result}


@router.get("/summary")
async def calibration_summary(
    batch_id: str = Query(...),
    topic_type: Optional[str] = Query("btc"),
):
    """
    Return quick calibration summary stats without full bucket data.
    Useful for the dashboard header metrics.
    """
    markets = db.get_resolved_markets(batch_id, topic_type=topic_type)
    if not markets:
        return {
            "success": True,
            "batch_id": batch_id,
            "topic_type": topic_type,
            "cached_count": 0,
            "stats": None,
            "message": "No data — run /api/markets/sync first.",
        }

    implied_probs = [m["implied_prob"] for m in markets if m.get("implied_prob") is not None]
    stats = cal.calibration_summary_stats(implied_probs)

    return {
        "success": True,
        "batch_id": batch_id,
        "topic_type": topic_type,
        "cached_count": len(markets),
        "stats": stats,
    }


@router.delete("/cache")
async def clear_calibration_cache(
    batch_id: str = Query(...),
    topic_type: Optional[str] = Query(None),
):
    """Clear cached calibration results so next /compute call re-runs fresh."""
    import sqlite3
    import os
    db_path = os.getenv("DB_PATH", "glass.db")
    with sqlite3.connect(db_path) as conn:
        if topic_type:
            conn.execute(
                "DELETE FROM calibration_cache WHERE batch_id=? AND topic_type=?",
                (batch_id, topic_type),
            )
        else:
            conn.execute(
                "DELETE FROM calibration_cache WHERE batch_id=?",
                (batch_id,),
            )
    return {"success": True, "message": "Calibration cache cleared."}
