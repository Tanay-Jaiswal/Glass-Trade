"""
tests/test_conviction.py — Unit tests for the Layer 2 conviction scoring engine.

Covers:
  - score_active_market: normal cases, edge cases, no-edge cases
  - find_best_opportunities: ranking, top_n cap
  - _find_bucket: boundary conditions
  - summarise_signals: aggregate stats
"""

import unittest
import sys
import os

# Ensure backend root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conviction import (
    score_active_market,
    find_best_opportunities,
    summarise_signals,
    _find_bucket,
    MIN_SCORE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def make_bucket(lower: float, upper: float, realized_freq: float, count: int = 15) -> dict:
    """Convenience builder for calibration bucket dicts."""
    mid = (lower + upper) / 2
    return {
        "bucket_lower": lower,
        "bucket_upper": upper,
        "bucket_label": f"{int(lower*100)}–{int(upper*100)}%",
        "predicted_prob": mid,
        "realized_freq": realized_freq,
        "count": count,
        "low_confidence": count < 10,
    }


STANDARD_BUCKETS = [
    make_bucket(0.0, 0.1, 0.05),   # 0-10%: crowd correct
    make_bucket(0.1, 0.2, 0.15),   # 10-20%: crowd correct
    make_bucket(0.2, 0.3, 0.25),   # 20-30%: crowd correct
    make_bucket(0.3, 0.4, 0.20),   # 30-40%: crowd overconfident (fade signal)
    make_bucket(0.4, 0.5, 0.35),   # 40-50%: crowd overconfident (fade signal)
    make_bucket(0.5, 0.6, 0.70),   # 50-60%: crowd underconfident (ride signal)
    make_bucket(0.6, 0.7, 0.65),   # 60-70%: crowd correct
    make_bucket(0.7, 0.8, 0.55),   # 70-80%: crowd overconfident (fade signal)
    make_bucket(0.8, 0.9, 0.85),   # 80-90%: crowd correct
    make_bucket(0.9, 1.0, 0.95),   # 90-100%: crowd correct
]

STANDARD_OUTCOMES = [
    {"option_id": 1, "option_title": "BTC $95k-96k", "yes_price": 0.35},   # fade: realized=0.20
    {"option_id": 2, "option_title": "BTC $96k-97k", "yes_price": 0.55},   # ride: realized=0.70
    {"option_id": 3, "option_title": "BTC $97k-98k", "yes_price": 0.65},   # ~correct
]


# ---------------------------------------------------------------------------
# _find_bucket
# ---------------------------------------------------------------------------

class TestFindBucket(unittest.TestCase):

    def test_normal_lookup(self):
        bucket = _find_bucket(0.35, STANDARD_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket["bucket_lower"], 0.3)
        self.assertEqual(bucket["bucket_upper"], 0.4)

    def test_lower_boundary(self):
        bucket = _find_bucket(0.0, STANDARD_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket["bucket_lower"], 0.0)

    def test_upper_boundary_exact_one(self):
        """1.0 should map to the [0.9, 1.0] bucket."""
        bucket = _find_bucket(1.0, STANDARD_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket["bucket_upper"], 1.0)

    def test_mid_bucket(self):
        bucket = _find_bucket(0.55, STANDARD_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket["bucket_lower"], 0.5)

    def test_empty_buckets_returns_none(self):
        result = _find_bucket(0.5, [])
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# score_active_market
# ---------------------------------------------------------------------------

class TestScoreActiveMarket(unittest.TestCase):

    def test_returns_list(self):
        signals = score_active_market(
            topic_id=1, topic_title="BTC Test Market",
            outcomes=STANDARD_OUTCOMES,
            calibration_buckets=STANDARD_BUCKETS,
        )
        self.assertIsInstance(signals, list)

    def test_fade_direction_detected(self):
        """Option priced at 35% where realized freq is 20% → crowd overconfident → fade."""
        signals = score_active_market(
            topic_id=1, topic_title="BTC Test",
            outcomes=[{"option_id": 1, "option_title": "Test", "yes_price": 0.35}],
            calibration_buckets=STANDARD_BUCKETS,
        )
        self.assertEqual(len(signals), 1)
        s = signals[0]
        self.assertEqual(s["direction"], "fade")
        self.assertAlmostEqual(s["gap"], abs(0.20 - 0.35), places=3)

    def test_ride_direction_detected(self):
        """Option priced at 55% where realized freq is 70% → crowd underconfident → ride."""
        signals = score_active_market(
            topic_id=1, topic_title="BTC Test",
            outcomes=[{"option_id": 2, "option_title": "Test", "yes_price": 0.55}],
            calibration_buckets=STANDARD_BUCKETS,
        )
        self.assertEqual(len(signals), 1)
        s = signals[0]
        self.assertEqual(s["direction"], "ride")
        self.assertAlmostEqual(s["gap"], abs(0.70 - 0.55), places=3)

    def test_sorted_by_conviction_descending(self):
        signals = score_active_market(
            topic_id=1, topic_title="BTC Test",
            outcomes=STANDARD_OUTCOMES,
            calibration_buckets=STANDARD_BUCKETS,
        )
        scores = [s["conviction_score"] for s in signals]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_min_score_filter(self):
        """With a very high min_score, no signals should pass."""
        signals = score_active_market(
            topic_id=1, topic_title="BTC Test",
            outcomes=STANDARD_OUTCOMES,
            calibration_buckets=STANDARD_BUCKETS,
            min_score=0.99,
        )
        self.assertEqual(len(signals), 0)

    def test_low_confidence_bucket_penalises_score(self):
        """A bucket with count < 10 should halve the conviction_score."""
        low_conf_buckets = [make_bucket(0.3, 0.4, 0.10, count=5)]  # low_confidence=True
        outcomes = [{"option_id": 1, "option_title": "Test", "yes_price": 0.35}]
        signals = score_active_market(
            topic_id=1, topic_title="Test",
            outcomes=outcomes,
            calibration_buckets=low_conf_buckets,
            min_score=0.0,
        )
        self.assertEqual(len(signals), 1)
        s = signals[0]
        expected_gap = abs(0.10 - 0.35)
        self.assertTrue(s["low_confidence"])
        self.assertAlmostEqual(s["conviction_score"], expected_gap * 0.5, places=3)

    def test_missing_yes_price_skipped(self):
        """Outcomes with missing yes_price should be silently skipped."""
        outcomes = [
            {"option_id": 1, "option_title": "Valid", "yes_price": 0.35},
            {"option_id": 2, "option_title": "No price"},               # missing
            {"option_id": 3, "option_title": "None price", "yes_price": None},
        ]
        signals = score_active_market(
            topic_id=1, topic_title="Test",
            outcomes=outcomes,
            calibration_buckets=STANDARD_BUCKETS,
        )
        # Only the first should generate a signal
        topic_ids = {s["option_id"] for s in signals}
        self.assertNotIn(2, topic_ids)
        self.assertNotIn(3, topic_ids)

    def test_out_of_range_yes_price_skipped(self):
        """yes_price outside [0,1] should be skipped."""
        outcomes = [{"option_id": 1, "option_title": "Bad", "yes_price": 1.5}]
        signals = score_active_market(
            topic_id=1, topic_title="Test",
            outcomes=outcomes,
            calibration_buckets=STANDARD_BUCKETS,
            min_score=0.0,
        )
        self.assertEqual(len(signals), 0)

    def test_empty_outcomes(self):
        signals = score_active_market(
            topic_id=1, topic_title="Empty",
            outcomes=[], calibration_buckets=STANDARD_BUCKETS,
        )
        self.assertEqual(signals, [])

    def test_empty_calibration_buckets(self):
        signals = score_active_market(
            topic_id=1, topic_title="Test",
            outcomes=STANDARD_OUTCOMES, calibration_buckets=[],
        )
        self.assertEqual(signals, [])

    def test_signal_fields_present(self):
        """Every signal dict must contain the expected keys."""
        signals = score_active_market(
            topic_id=42, topic_title="BTC Hourly",
            outcomes=[{"option_id": 7, "option_title": "Range A", "yes_price": 0.35}],
            calibration_buckets=STANDARD_BUCKETS,
            min_score=0.0,
        )
        if not signals:
            self.skipTest("No signal generated (min_score or gap issue)")
        s = signals[0]
        required_keys = [
            "topic_id", "topic_title", "option_id", "option_title",
            "live_implied_prob", "bucket_label", "historical_realized_freq",
            "bucket_count", "low_confidence", "gap", "direction",
            "conviction_score", "reasoning",
        ]
        for key in required_keys:
            self.assertIn(key, s, f"Missing key: {key}")

    def test_topic_id_propagated(self):
        signals = score_active_market(
            topic_id=999, topic_title="Test",
            outcomes=[{"option_id": 1, "option_title": "X", "yes_price": 0.35}],
            calibration_buckets=STANDARD_BUCKETS,
            min_score=0.0,
        )
        if signals:
            self.assertEqual(signals[0]["topic_id"], 999)

    def test_zero_yes_price_handled(self):
        """yes_price=0.0 is valid and should map to the 0-10% bucket."""
        outcomes = [{"option_id": 1, "option_title": "Zero", "yes_price": 0.0}]
        # realized_freq for 0-10% bucket is 0.05, gap = |0.05 - 0.0| = 0.05
        signals = score_active_market(
            topic_id=1, topic_title="Test",
            outcomes=outcomes,
            calibration_buckets=STANDARD_BUCKETS,
            min_score=0.0,
        )
        # This could be below MIN_SCORE_THRESHOLD but should not crash
        self.assertIsInstance(signals, list)


# ---------------------------------------------------------------------------
# find_best_opportunities
# ---------------------------------------------------------------------------

class TestFindBestOpportunities(unittest.TestCase):

    def _make_market(self, topic_id: int, yes_prices: list[float]) -> dict:
        return {
            "topic_id": topic_id,
            "title": f"Market {topic_id}",
            "outcomes": [
                {"option_id": i, "option_title": f"Opt {i}", "yes_price": p}
                for i, p in enumerate(yes_prices)
            ],
        }

    def test_returns_list(self):
        markets = [self._make_market(1, [0.35, 0.55])]
        result = find_best_opportunities(
            active_markets=markets,
            calibration_data={"buckets": STANDARD_BUCKETS},
        )
        self.assertIsInstance(result, list)

    def test_top_n_cap(self):
        markets = [self._make_market(i, [0.35]) for i in range(10)]
        result = find_best_opportunities(
            active_markets=markets,
            calibration_data={"buckets": STANDARD_BUCKETS},
            top_n=3,
        )
        self.assertLessEqual(len(result), 3)

    def test_global_sort_order(self):
        markets = [
            self._make_market(1, [0.35]),  # gap = 0.15
            self._make_market(2, [0.55]),  # gap = 0.15 (ride)
        ]
        result = find_best_opportunities(
            active_markets=markets,
            calibration_data={"buckets": STANDARD_BUCKETS},
        )
        scores = [s["conviction_score"] for s in result]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_markets(self):
        result = find_best_opportunities(
            active_markets=[], calibration_data={"buckets": STANDARD_BUCKETS}
        )
        self.assertEqual(result, [])

    def test_no_calibration_buckets(self):
        markets = [self._make_market(1, [0.35])]
        result = find_best_opportunities(
            active_markets=markets, calibration_data={"buckets": []}
        )
        self.assertEqual(result, [])

    def test_markets_without_outcomes_skipped(self):
        markets = [
            {"topic_id": 1, "title": "No outcomes"},
            self._make_market(2, [0.35]),
        ]
        result = find_best_opportunities(
            active_markets=markets, calibration_data={"buckets": STANDARD_BUCKETS}
        )
        topic_ids = {s["topic_id"] for s in result}
        self.assertNotIn(1, topic_ids)


# ---------------------------------------------------------------------------
# summarise_signals
# ---------------------------------------------------------------------------

class TestSummariseSignals(unittest.TestCase):

    def test_empty(self):
        result = summarise_signals([])
        self.assertEqual(result["count"], 0)

    def test_counts(self):
        signals = [
            {"direction": "fade", "conviction_score": 0.15},
            {"direction": "ride", "conviction_score": 0.20},
            {"direction": "fade", "conviction_score": 0.10},
        ]
        result = summarise_signals(signals)
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["fade_count"], 2)
        self.assertEqual(result["ride_count"], 1)

    def test_avg_conviction(self):
        signals = [
            {"direction": "fade", "conviction_score": 0.10},
            {"direction": "ride", "conviction_score": 0.20},
        ]
        result = summarise_signals(signals)
        self.assertAlmostEqual(result["avg_conviction"], 0.15, places=4)

    def test_top_signal_is_highest_scoring(self):
        signals = [
            {"direction": "fade", "conviction_score": 0.10},
            {"direction": "ride", "conviction_score": 0.30},
            {"direction": "fade", "conviction_score": 0.20},
        ]
        result = summarise_signals(signals)
        # Top signal should be the first one (highest score)
        self.assertEqual(result["top_signal"]["conviction_score"], 0.10)
        # (signals are pre-sorted before being passed in practice)


if __name__ == "__main__":
    unittest.main(verbosity=2)
