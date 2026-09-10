"""
test_calibration.py — Unit tests for the calibration module.

These tests verify the core intellectual contribution of Glass:
the implied probability computation, bucketing logic, and Brier score math.
All expected values are hand-calculated so failures are unambiguous.

Run with:
    python -m unittest discover -s tests -p "test_*.py" -v
or:
    pytest tests/test_calibration.py -v
"""

import math
import sys
import os
import unittest

# Ensure we can import calibration from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import calibration as cal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_market(
    topic_id: int,
    resolved_option_id: int,
    shares: list[tuple[int, float]],  # list of (option_id, shares)
    implied_prob: float = None,
) -> dict:
    """Build a minimal market dict for testing."""
    outcomes = [{"option_id": oid, "name": str(oid), "shares": s} for oid, s in shares]
    m = {
        "topic_id": topic_id,
        "resolved_option_id": resolved_option_id,
        "outcomes": outcomes,
    }
    if implied_prob is not None:
        m["implied_prob"] = implied_prob
    return m


# ---------------------------------------------------------------------------
# compute_implied_prob
# ---------------------------------------------------------------------------

class TestComputeImpliedProb(unittest.TestCase):
    def test_simple_two_outcome(self):
        """Winner has 3 shares, loser has 1 → 75%."""
        outcomes = [
            {"option_id": 1, "shares": 3},
            {"option_id": 2, "shares": 1},
        ]
        self.assertAlmostEqual(cal.compute_implied_prob(outcomes, resolved_option_id=1), 0.75, places=5)

    def test_uniform_distribution(self):
        """All 5 outcomes have equal shares → winner is 20%."""
        outcomes = [{"option_id": i, "shares": 10} for i in range(5)]
        result = cal.compute_implied_prob(outcomes, resolved_option_id=3)
        self.assertAlmostEqual(result, 0.2, places=6)

    def test_winner_takes_all(self):
        """Winner has all shares → 100%."""
        outcomes = [
            {"option_id": 1, "shares": 100},
            {"option_id": 2, "shares": 0},
            {"option_id": 3, "shares": 0},
        ]
        self.assertAlmostEqual(cal.compute_implied_prob(outcomes, resolved_option_id=1), 1.0, places=5)

    def test_winner_has_zero_shares(self):
        """Edge case: winner has zero shares → 0%."""
        outcomes = [
            {"option_id": 1, "shares": 0},
            {"option_id": 2, "shares": 50},
        ]
        self.assertAlmostEqual(cal.compute_implied_prob(outcomes, resolved_option_id=1), 0.0, places=5)

    def test_no_outcomes_returns_none(self):
        self.assertIsNone(cal.compute_implied_prob([], resolved_option_id=1))

    def test_none_resolved_id_returns_none(self):
        outcomes = [{"option_id": 1, "shares": 10}]
        self.assertIsNone(cal.compute_implied_prob(outcomes, resolved_option_id=None))

    def test_zero_total_shares_returns_none(self):
        outcomes = [{"option_id": 1, "shares": 0}, {"option_id": 2, "shares": 0}]
        self.assertIsNone(cal.compute_implied_prob(outcomes, resolved_option_id=1))

    def test_resolved_id_not_in_outcomes_returns_none(self):
        outcomes = [{"option_id": 1, "shares": 10}]
        self.assertIsNone(cal.compute_implied_prob(outcomes, resolved_option_id=99))

    def test_500_outcome_market_typical(self):
        """Typical BTC market: 500 outcomes, winner has modest but above-baseline shares."""
        outcomes = [{"option_id": i, "shares": 40} for i in range(1, 501)]  # 40 each = baseline ~0.2%
        outcomes[184 - 1]["shares"] = 200  # winner has 5x more
        total = 40 * 499 + 200  # 19960 + 200 = 20160
        expected = 200 / 20160
        result = cal.compute_implied_prob(outcomes, resolved_option_id=184)
        self.assertAlmostEqual(result, expected, places=7)


# ---------------------------------------------------------------------------
# brier_score
# ---------------------------------------------------------------------------

class TestBrierScore(unittest.TestCase):
    def test_perfect_calibration(self):
        """All markets priced winner at 100% → BS = 0."""
        probs = [1.0, 1.0, 1.0]
        self.assertAlmostEqual(cal.brier_score(probs), 0.0, places=5)

    def test_uniform_ignorance(self):
        """All markets priced winner at 0% → BS = 1."""
        probs = [0.0, 0.0, 0.0]
        self.assertAlmostEqual(cal.brier_score(probs), 1.0, places=5)

    def test_coin_flip_baseline(self):
        """All markets at 50% → BS = 0.25."""
        probs = [0.5] * 100
        self.assertAlmostEqual(cal.brier_score(probs), 0.25, places=6)

    def test_hand_calculated_mixed(self):
        """
        Three markets: p=0.8, p=0.6, p=0.2
        BS = mean((1-0.8)^2, (1-0.6)^2, (1-0.2)^2)
           = mean(0.04, 0.16, 0.64)
           = 0.84 / 3 = 0.28
        """
        probs = [0.8, 0.6, 0.2]
        expected = (0.04 + 0.16 + 0.64) / 3
        self.assertAlmostEqual(cal.brier_score(probs), expected, places=6)

    def test_empty_returns_nan(self):
        result = cal.brier_score([])
        self.assertTrue(math.isnan(result))

    def test_single_value(self):
        self.assertAlmostEqual(cal.brier_score([0.7]), (1 - 0.7) ** 2, places=6)


# ---------------------------------------------------------------------------
# bucket_markets
# ---------------------------------------------------------------------------

class TestBucketMarkets(unittest.TestCase):
    def test_basic_bucketing(self):
        """Markets at 5%, 15%, 85% go into buckets 0-10%, 10-20%, 80-90%."""
        markets = [
            {"implied_prob": 0.05},
            {"implied_prob": 0.15},
            {"implied_prob": 0.85},
        ]
        buckets = cal.bucket_markets(markets, n_buckets=10)
        self.assertEqual(len(buckets), 10)

        b0 = buckets[0]  # 0-10%
        self.assertEqual(b0["count"], 1)
        self.assertAlmostEqual(b0["predicted_prob"], 0.05, places=5)

        b1 = buckets[1]  # 10-20%
        self.assertEqual(b1["count"], 1)

        b8 = buckets[8]  # 80-90%
        self.assertEqual(b8["count"], 1)

    def test_empty_buckets_included(self):
        """All 10 buckets should be present even if empty."""
        markets = [{"implied_prob": 0.5}]
        buckets = cal.bucket_markets(markets, n_buckets=10)
        self.assertEqual(len(buckets), 10)
        non_empty = [b for b in buckets if b["count"] > 0]
        self.assertEqual(len(non_empty), 1)

    def test_low_confidence_flag(self):
        """Buckets with < MIN_BUCKET_SIZE markets should be flagged."""
        markets = [{"implied_prob": 0.5}]  # only 1 market
        buckets = cal.bucket_markets(markets, n_buckets=10)
        populated = [b for b in buckets if b["count"] > 0][0]
        self.assertTrue(populated["low_confidence"])

    def test_high_confidence_bucket(self):
        """A bucket with ≥ MIN_BUCKET_SIZE markets should NOT be flagged."""
        markets = [{"implied_prob": 0.55} for _ in range(cal.MIN_BUCKET_SIZE + 5)]
        buckets = cal.bucket_markets(markets, n_buckets=10)
        populated = [b for b in buckets if b["count"] > 0][0]
        self.assertFalse(populated["low_confidence"])

    def test_boundary_value_100pct(self):
        """An implied_prob of exactly 1.0 should fall in the last bucket."""
        markets = [{"implied_prob": 1.0}]
        buckets = cal.bucket_markets(markets, n_buckets=10)
        self.assertEqual(buckets[-1]["count"], 1)

    def test_none_implied_prob_skipped(self):
        """Markets with None implied_prob should be silently skipped."""
        markets = [
            {"implied_prob": None},
            {"implied_prob": 0.3},
            {},
        ]
        buckets = cal.bucket_markets(markets, n_buckets=10)
        total_count = sum(b["count"] for b in buckets)
        self.assertEqual(total_count, 1)

    def test_bucket_labels(self):
        """Check bucket labels are formatted correctly."""
        markets = [{"implied_prob": 0.05}]
        buckets = cal.bucket_markets(markets, n_buckets=10)
        self.assertEqual(buckets[0]["bucket_label"], "0–10%")
        self.assertEqual(buckets[9]["bucket_label"], "90–100%")

    def test_5_buckets(self):
        """Verify n_buckets parameter works for non-default bucket count."""
        markets = [{"implied_prob": 0.1}, {"implied_prob": 0.5}, {"implied_prob": 0.9}]
        buckets = cal.bucket_markets(markets, n_buckets=5)
        self.assertEqual(len(buckets), 5)
        total_count = sum(b["count"] for b in buckets)
        self.assertEqual(total_count, 3)


# ---------------------------------------------------------------------------
# compute_calibration (integration)
# ---------------------------------------------------------------------------

class TestComputeCalibration(unittest.TestCase):
    def test_returns_expected_keys(self):
        markets = [
            make_market(1, 1, [(1, 80), (2, 20)]),
            make_market(2, 1, [(1, 60), (2, 40)]),
        ]
        result = cal.compute_calibration(markets)
        self.assertIn("brier_score", result)
        self.assertIn("buckets", result)
        self.assertIn("insight", result)
        self.assertIn("total_markets", result)
        self.assertIn("markets_with_data", result)
        self.assertIn("methodology_note", result)

    def test_total_vs_with_data(self):
        """total_markets includes those with missing data; markets_with_data excludes them."""
        markets = [
            make_market(1, 1, [(1, 80), (2, 20)]),   # has data
            {"topic_id": 2, "resolved_option_id": None, "outcomes": []},  # no data
        ]
        result = cal.compute_calibration(markets)
        self.assertEqual(result["total_markets"], 2)
        self.assertEqual(result["markets_with_data"], 1)

    def test_brier_score_range(self):
        """Brier score must always be in [0, 1]."""
        import random
        random.seed(42)
        markets = [
            make_market(i, 1, [(1, random.uniform(1, 100)), (2, random.uniform(1, 100))])
            for i in range(50)
        ]
        result = cal.compute_calibration(markets)
        self.assertGreaterEqual(result["brier_score"], 0.0)
        self.assertLessEqual(result["brier_score"], 1.0)

    def test_pre_computed_implied_prob_used(self):
        """If market already has implied_prob set, it should be used directly."""
        markets = [{"topic_id": 1, "implied_prob": 0.75, "resolved_option_id": 1, "outcomes": []}]
        result = cal.compute_calibration(markets)
        self.assertEqual(result["markets_with_data"], 1)
        expected_bs = (1 - 0.75) ** 2
        self.assertAlmostEqual(result["brier_score"], expected_bs, places=6)


if __name__ == "__main__":
    unittest.main()
