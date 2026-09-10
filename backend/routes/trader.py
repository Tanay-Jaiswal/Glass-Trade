"""
routes/trader.py — Layer 3: Trade evaluation and execution endpoints.

POST /api/trader/evaluate  — score a live market outcome, get cost estimate (no trade)
POST /api/trader/execute   — evaluate + optionally execute (requires dry_run=false)
GET  /api/trader/history   — return trade log
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import database as db
from api_client import GlimpseClient, GlimpseAPIError
from conviction import score_active_market
from trader import TradeConfig, evaluate_and_trade

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trader", tags=["trader"])


def _get_client() -> Optional[GlimpseClient]:
    api_key = os.getenv("GLIMPSE_API_KEY", "")
    if not api_key or api_key == "paste_your_key_here":
        return None
    return GlimpseClient(api_key=api_key)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    topic_id: int = Field(..., description="Glimpse topic/market ID")
    option_id: int = Field(..., description="Specific outcome/option to evaluate")
    topic_title: str = Field("", description="Human-readable market title")
    option_title: str = Field("", description="Human-readable option label")
    live_implied_prob: float = Field(..., ge=0.0, le=1.0, description="Current yes_price from live quotes")
    calibration_buckets: list[dict] = Field(..., description="Calibration buckets from /api/calibration/compute")
    contracts: int = Field(1, ge=1, le=50, description="Number of contracts to evaluate")
    min_conviction: float = Field(0.10, ge=0.0, le=1.0)
    min_bucket_count: int = Field(10, ge=1)
    max_contracts: int = Field(5, ge=1, le=50)


class ExecuteRequest(EvaluateRequest):
    dry_run: bool = Field(
        True,
        description="Set to false to execute a real trade. Default true (safe).",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/evaluate")
async def evaluate_signal(req: EvaluateRequest):
    """
    Evaluate a conviction signal and return a cost estimate.
    Does NOT execute any trade — safe to call freely.
    """
    # Build a minimal signal manually from the request
    # (in production the UI passes signals straight from the /signals endpoint)
    outcome = {
        "option_id": req.option_id,
        "option_title": req.option_title or f"Option {req.option_id}",
        "yes_price": req.live_implied_prob,
    }
    signals = score_active_market(
        topic_id=req.topic_id,
        topic_title=req.topic_title or f"Market {req.topic_id}",
        outcomes=[outcome],
        calibration_buckets=req.calibration_buckets,
        min_score=0.0,  # include all for evaluate — risk gate handles the rest
    )

    if not signals:
        return {
            "success": False,
            "message": "No scorable signal from provided data (check calibration buckets).",
            "signal": None,
            "decision": None,
        }

    signal = signals[0]
    config = TradeConfig(
        min_conviction=req.min_conviction,
        min_bucket_count=req.min_bucket_count,
        max_contracts=req.max_contracts,
        default_contracts=req.contracts,
        dry_run=True,  # always dry_run in evaluate
    )

    client = _get_client()
    try:
        if client:
            async with client:
                decision = await evaluate_and_trade(signal, config, client, contracts=req.contracts)
        else:
            decision = await evaluate_and_trade(signal, config, None, contracts=req.contracts)
        return {"success": True, "signal": signal, "decision": decision.to_dict()}
    except GlimpseAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/execute")
async def execute_signal(req: ExecuteRequest):
    """
    Evaluate a conviction signal and optionally execute a trade.

    dry_run=true (default): logs the decision, returns cost estimate, NO real trade.
    dry_run=false:          executes a real trade on Glimpse. Use with extreme caution.
    """
    outcome = {
        "option_id": req.option_id,
        "option_title": req.option_title or f"Option {req.option_id}",
        "yes_price": req.live_implied_prob,
    }
    signals = score_active_market(
        topic_id=req.topic_id,
        topic_title=req.topic_title or f"Market {req.topic_id}",
        outcomes=[outcome],
        calibration_buckets=req.calibration_buckets,
        min_score=0.0,
    )

    if not signals:
        return {
            "success": False,
            "message": "No scorable signal from provided data.",
            "signal": None,
            "decision": None,
        }

    signal = signals[0]
    config = TradeConfig(
        min_conviction=req.min_conviction,
        min_bucket_count=req.min_bucket_count,
        max_contracts=req.max_contracts,
        default_contracts=req.contracts,
        dry_run=req.dry_run,   # honour the caller's explicit choice
    )

    mode = "DRY RUN" if req.dry_run else "🔴 LIVE EXECUTION"
    logger.info("Trade request received [%s]: topic=%s option=%s", mode, req.topic_id, req.option_id)

    client = _get_client()
    if not req.dry_run and not client:
        raise HTTPException(
            status_code=400,
            detail="Live trade execution requires GLIMPSE_API_KEY configured in backend/.env",
        )

    try:
        if client:
            async with client:
                decision = await evaluate_and_trade(signal, config, client, contracts=req.contracts)
        else:
            decision = await evaluate_and_trade(signal, config, None, contracts=req.contracts)
        return {
            "success": True,
            "mode": mode,
            "signal": signal,
            "decision": decision.to_dict(),
        }
    except GlimpseAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/history")
async def get_trade_history(limit: int = 50):
    """Return the most recent trade decisions (dry-run and executed)."""
    trades = db.get_trade_history(limit=limit)
    return {
        "success": True,
        "count": len(trades),
        "trades": trades,
    }
