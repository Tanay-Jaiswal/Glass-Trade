"""
conviction.py — Layer 2: Conviction Score & Signal Engine for Glass.

The core question:
  "Given a live market's current implied probability distribution,
   does the calibration history tell us the crowd is systematically wrong?"

How it works
------------
1. For each live outcome in an active market, compute its current implied prob
   from live quote data (yes_price acts as a direct probability proxy).

2. Look up which historical calibration bucket that probability falls into
   (e.g., 60% implied prob → bucket [60%, 70%]).

3. Compute the gap:
     gap = abs(historical_realized_freq - live_implied_prob)

   A large gap means the crowd is historically wrong at this confidence level.

4. Determine direction:
   - "fade"  → crowd is OVERCONFIDENT. Historical realized_freq < implied_prob.
                Bet AGAINST the crowd's favourite (buy NO, or buy a competing outcome).
   - "ride"  → crowd is UNDERCONFIDENT. Historical realized_freq > implied_prob.
                Bet WITH the crowd but they are underpricing the favourite (buy YES).

5. Conviction score = gap (range 0.0–1.0). Higher = stronger edge in expectation.

Caveats
-------
- Calibration is based on historical closing-price data, not intra-market snapshots.
- Buckets with low_confidence=True (< 10 markets) are explicitly penalised.
- This is a statistical edge over large samples — not a guarantee per trade.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum calibration bucket count to trust the historical signal
MIN_BUCKET_CONFIDENCE = 10

# Minimum gap to consider a market worth flagging
MIN_SCORE_THRESHOLD = 0.05


def _find_bucket(implied_prob: float, buckets: list[dict]) -> Optional[dict]:
    """
    Return the calibration bucket that contains the given implied probability.
    """
    for b in buckets:
        lower = b.get("bucket_lower", 0)
        upper = b.get("bucket_upper", 1)
        if lower <= implied_prob < upper or (implied_prob == 1.0 and upper == 1.0):
            return b
    return None


def score_active_market(
    topic_id: int,
    topic_title: str,
    outcomes: list[dict],
    calibration_buckets: list[dict],
    min_score: float = MIN_SCORE_THRESHOLD,
) -> list[dict]:
    """
    Score each outcome of a live active market against the calibration history.

    Args:
        topic_id: The Glimpse topic/market ID.
        topic_title: Human-readable market title.
        outcomes: List of outcome dicts from the live quotes API. Each should have:
                  - option_id (int)
                  - option_title (str) — the outcome label
                  - yes_price (float) — current market price in [0,1], acts as prob
                  - shares (float, optional) — outstanding shares
        calibration_buckets: Output of compute_calibration()["buckets"] for the batch.
        min_score: Minimum conviction gap to include in output.

    Returns:
        List of ConvictionSignal dicts, sorted by conviction_score descending.
        Each signal has:
          - topic_id, topic_title, option_id, option_title
          - live_implied_prob: float — current market consensus probability
          - bucket_label: str — which historical bucket this falls into
          - historical_realized_freq: float | None
          - bucket_count: int — how many markets in the historical bucket
          - low_confidence: bool — True if bucket has < MIN_BUCKET_CONFIDENCE markets
          - gap: float — abs(historical_realized_freq - live_implied_prob)
          - direction: "fade" | "ride" | "neutral"
          - conviction_score: float — gap penalised by low_confidence flag
          - reasoning: str — plain-English explanation
    """
    signals = []

    for outcome in outcomes:
        yes_price = outcome.get("yes_price")
        option_id = outcome.get("option_id")
        option_title = outcome.get("option_title", f"Option {option_id}")

        # yes_price is the direct probability proxy (0.0 = 0%, 1.0 = 100%)
        if yes_price is None or not (0.0 <= yes_price <= 1.0):
            continue

        implied_prob = yes_price
        bucket = _find_bucket(implied_prob, calibration_buckets)

        if bucket is None:
            logger.debug("No bucket found for implied_prob=%.4f", implied_prob)
            continue

        realized_freq = bucket.get("realized_freq")
        bucket_count = bucket.get("count", 0)
        low_confidence = bucket.get("low_confidence", True)
        bucket_label = bucket.get("bucket_label", "?")

        # Can't score if we have no historical data in this bucket
        if realized_freq is None or bucket_count == 0:
            continue

        gap = abs(realized_freq - implied_prob)

        # Determine direction
        if realized_freq < implied_prob:
            direction = "fade"   # crowd is overconfident — bet against
        elif realized_freq > implied_prob:
            direction = "ride"   # crowd is underconfident — bet with
        else:
            direction = "neutral"

        # Penalise low-confidence buckets by halving the score
        conviction_score = gap * (0.5 if low_confidence else 1.0)

        if conviction_score < min_score:
            continue

        # Plain-English reasoning
        crowd_pct = round(implied_prob * 100, 1)
        hist_pct = round(realized_freq * 100, 1)
        if direction == "fade":
            reasoning = (
                f"Crowd prices this at {crowd_pct}%, but historically outcomes "
                f"at this confidence level only resolve true {hist_pct}% of the time. "
                f"Crowd is overconfident — edge to fade."
            )
        elif direction == "ride":
            reasoning = (
                f"Crowd prices this at {crowd_pct}%, but historically outcomes "
                f"at this confidence level resolve true {hist_pct}% of the time. "
                f"Crowd is underconfident — edge to ride."
            )
        else:
            reasoning = f"Crowd pricing matches historical calibration (~{crowd_pct}%). No clear edge."

        if low_confidence:
            reasoning += f" ⚠️ Low confidence: only {bucket_count} markets in this historical bucket."

        signals.append({
            "topic_id": topic_id,
            "topic_title": topic_title,
            "option_id": option_id,
            "option_title": option_title,
            "live_implied_prob": round(implied_prob, 4),
            "bucket_label": bucket_label,
            "historical_realized_freq": round(realized_freq, 4),
            "bucket_count": bucket_count,
            "low_confidence": low_confidence,
            "gap": round(gap, 4),
            "direction": direction,
            "conviction_score": round(conviction_score, 4),
            "reasoning": reasoning,
        })

    # Sort by conviction score descending
    signals.sort(key=lambda s: s["conviction_score"], reverse=True)
    return signals


def find_best_opportunities(
    active_markets: list[dict],
    calibration_data: dict,
    min_score: float = MIN_SCORE_THRESHOLD,
    top_n: int = 20,
) -> list[dict]:
    """
    Scan all active markets and return the top N opportunities by conviction score.

    Args:
        active_markets: List of active market dicts from the Glimpse API.
                        Each should have 'topic_id', 'title', and 'outcomes' (with yes_price).
        calibration_data: Full output of compute_calibration() — needs 'buckets'.
        min_score: Minimum conviction_score to include.
        top_n: Maximum number of opportunities to return.

    Returns:
        Flat ranked list of ConvictionSignal dicts (best first).
    """
    buckets = calibration_data.get("buckets", [])
    if not buckets:
        logger.warning("No calibration buckets available — cannot score opportunities.")
        return []

    all_signals = []
    for market in active_markets:
        topic_id = market.get("topic_id") or market.get("id")
        topic_title = market.get("title") or market.get("topic_title") or f"Market {topic_id}"
        outcomes = market.get("outcomes") or market.get("options") or []

        if not outcomes:
            continue

        signals = score_active_market(
            topic_id=topic_id,
            topic_title=topic_title,
            outcomes=outcomes,
            calibration_buckets=buckets,
            min_score=min_score,
        )
        all_signals.extend(signals)

    # Global sort and cap
    all_signals.sort(key=lambda s: s["conviction_score"], reverse=True)
    return all_signals[:top_n]


def summarise_signals(signals: list[dict]) -> dict:
    """
    Return aggregate stats for a list of signals — useful for the API response.
    """
    if not signals:
        return {"count": 0, "avg_conviction": 0, "fade_count": 0, "ride_count": 0}

    fade = [s for s in signals if s["direction"] == "fade"]
    ride = [s for s in signals if s["direction"] == "ride"]
    avg_conviction = sum(s["conviction_score"] for s in signals) / len(signals)

    return {
        "count": len(signals),
        "avg_conviction": round(avg_conviction, 4),
        "fade_count": len(fade),
        "ride_count": len(ride),
        "top_signal": signals[0] if signals else None,
    }
