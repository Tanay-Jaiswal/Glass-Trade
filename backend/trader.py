"""
trader.py — Layer 3: Risk-gated Trade Execution Engine for Glass.

Flow
----
1. Receive a ConvictionSignal (from conviction.py).
2. Check it passes risk gates (min_conviction, min_bucket_count).
3. Call estimate_trade() to get the cost preview — always.
4. If dry_run=True (default): log the decision and return without executing.
5. If dry_run=False: call execute_trade() and log the full result.

Safety design
-------------
- dry_run=True is the hardcoded default in TradeConfig.
- The execute endpoint requires an explicit `"dry_run": false` in the request body.
- The max_contracts cap limits per-trade exposure.
- All decisions (dry-run and live) are written to the SQLite trades table.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import database as db
from api_client import GlimpseClient, GlimpseAPIError

logger = logging.getLogger(__name__)


@dataclass
class TradeConfig:
    """
    Risk parameters for the trade executor.

    Attributes:
        min_conviction:   Minimum conviction_score (0.0–1.0) to accept a signal.
        min_bucket_count: Minimum historical bucket sample size to trust the signal.
        max_contracts:    Maximum contracts to trade per signal.
        dry_run:          If True (default), evaluate but never execute real trade.
        default_contracts: Default number of contracts when not specified.
    """
    min_conviction: float = 0.10
    min_bucket_count: int = 10
    max_contracts: int = 5
    dry_run: bool = True
    default_contracts: int = 1


@dataclass
class TradeDecision:
    """
    The full output of evaluate_and_trade() — both the analysis and the execution result.
    """
    signal: dict
    passed_risk_gate: bool
    risk_gate_reason: str
    cost_estimate: Optional[dict]
    dry_run: bool
    executed: bool
    api_result: Optional[dict]
    trade_id: Optional[int]
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "passed_risk_gate": self.passed_risk_gate,
            "risk_gate_reason": self.risk_gate_reason,
            "cost_estimate": self.cost_estimate,
            "dry_run": self.dry_run,
            "executed": self.executed,
            "api_result": self.api_result,
            "trade_id": self.trade_id,
            "error": self.error,
        }


def _check_risk_gate(signal: dict, config: TradeConfig) -> tuple[bool, str]:
    """
    Apply risk rules to a signal. Returns (passed, reason_string).
    """
    score = signal.get("conviction_score", 0)
    if score < config.min_conviction:
        return False, (
            f"Conviction score {score:.3f} below threshold {config.min_conviction:.3f}."
        )

    bucket_count = signal.get("bucket_count", 0)
    if bucket_count < config.min_bucket_count:
        return False, (
            f"Historical bucket has only {bucket_count} markets "
            f"(minimum required: {config.min_bucket_count}). Signal not statistically reliable."
        )

    direction = signal.get("direction", "neutral")
    if direction == "neutral":
        return False, "Signal direction is neutral — no exploitable edge detected."

    return True, "Passed all risk gates."


def _derive_prediction(direction: str) -> str:
    """
    Translate conviction direction to a Glimpse trade prediction.
    - "fade"  → bet AGAINST the crowd's favourite → buy 'no'
    - "ride"  → bet WITH the underpriced outcome  → buy 'yes'
    """
    return "no" if direction == "fade" else "yes"


async def evaluate_and_trade(
    signal: dict,
    config: TradeConfig,
    client: GlimpseClient,
    contracts: Optional[int] = None,
) -> TradeDecision:
    """
    The main entry point: evaluate a conviction signal and optionally execute a trade.

    Args:
        signal:    A ConvictionSignal dict from conviction.score_active_market().
        config:    Risk configuration (min_conviction, max_contracts, dry_run flag).
        client:    An open GlimpseClient (already inside async context).
        contracts: Number of contracts to trade. Defaults to config.default_contracts.

    Returns:
        TradeDecision with full audit trail.
    """
    topic_id = signal["topic_id"]
    option_id = signal["option_id"]
    topic_title = signal.get("topic_title", f"Market {topic_id}")
    option_title = signal.get("option_title", f"Option {option_id}")
    direction = signal.get("direction", "neutral")
    prediction = _derive_prediction(direction)
    n_contracts = min(contracts or config.default_contracts, config.max_contracts)

    # ── Risk gate ────────────────────────────────────────────────────────────
    passed, reason = _check_risk_gate(signal, config)
    if not passed:
        logger.info("Risk gate rejected signal for %s (%s): %s", topic_title, option_title, reason)
        trade_id = db.insert_trade_log(
            topic_id=topic_id, option_id=option_id,
            topic_title=topic_title, option_title=option_title,
            prediction=prediction, trade_type="buy",
            contracts=n_contracts,
            conviction_score=signal.get("conviction_score"),
            direction=direction,
            live_implied_prob=signal.get("live_implied_prob"),
            cost_estimate=None, dry_run=True, executed=False,
            api_result=None, signal=signal,
        )
        return TradeDecision(
            signal=signal, passed_risk_gate=False, risk_gate_reason=reason,
            cost_estimate=None, dry_run=True, executed=False,
            api_result=None, trade_id=trade_id,
        )

    # ── Cost estimate (always) ───────────────────────────────────────────────
    cost_estimate = None
    try:
        cost_estimate = await client.estimate_trade(
            topic_id=topic_id,
            option_id=option_id,
            contracts=n_contracts,
            prediction=prediction,
            trade_type="buy",
        )
        logger.info(
            "Trade estimate for %s [%s] → %s×%d contracts: %s",
            topic_title, option_title, prediction.upper(), n_contracts, cost_estimate,
        )
    except GlimpseAPIError as exc:
        logger.warning("estimate_trade failed: %s", exc)
        cost_estimate = {"error": str(exc)}

    # ── Dry run gate ─────────────────────────────────────────────────────────
    if config.dry_run:
        logger.info("DRY RUN — not executing trade for %s (%s)", topic_title, option_title)
        trade_id = db.insert_trade_log(
            topic_id=topic_id, option_id=option_id,
            topic_title=topic_title, option_title=option_title,
            prediction=prediction, trade_type="buy",
            contracts=n_contracts,
            conviction_score=signal.get("conviction_score"),
            direction=direction,
            live_implied_prob=signal.get("live_implied_prob"),
            cost_estimate=_extract_cost(cost_estimate),
            dry_run=True, executed=False,
            api_result=cost_estimate, signal=signal,
        )
        return TradeDecision(
            signal=signal, passed_risk_gate=True, risk_gate_reason=reason,
            cost_estimate=cost_estimate, dry_run=True, executed=False,
            api_result=None, trade_id=trade_id,
        )

    # ── Live execution ────────────────────────────────────────────────────────
    api_result = None
    executed = False
    error = None
    try:
        logger.warning(
            "🔴 LIVE TRADE EXECUTING: %s %s×%d %s on %s (%s)",
            prediction.upper(), n_contracts, n_contracts, "contracts",
            topic_title, option_title,
        )
        api_result = await client.execute_trade(
            topic_id=topic_id,
            option_id=option_id,
            contracts=n_contracts,
            prediction=prediction,
            trade_type="buy",
        )
        executed = True
        logger.info("Trade executed successfully: %s", api_result)
    except GlimpseAPIError as exc:
        error = str(exc)
        api_result = {"error": error}
        logger.error("execute_trade failed: %s", exc)

    trade_id = db.insert_trade_log(
        topic_id=topic_id, option_id=option_id,
        topic_title=topic_title, option_title=option_title,
        prediction=prediction, trade_type="buy",
        contracts=n_contracts,
        conviction_score=signal.get("conviction_score"),
        direction=direction,
        live_implied_prob=signal.get("live_implied_prob"),
        cost_estimate=_extract_cost(cost_estimate),
        dry_run=False, executed=executed,
        api_result=api_result, signal=signal,
    )

    return TradeDecision(
        signal=signal, passed_risk_gate=True, risk_gate_reason=reason,
        cost_estimate=cost_estimate, dry_run=False, executed=executed,
        api_result=api_result, trade_id=trade_id, error=error,
    )


def _extract_cost(estimate: Optional[dict]) -> Optional[float]:
    """Try to pull a numeric cost from the estimate API response."""
    if not estimate or "error" in estimate:
        return None
    # Common field names from Glimpse estimate endpoint
    for key in ("total_cost", "cost", "amount", "price"):
        val = estimate.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None
