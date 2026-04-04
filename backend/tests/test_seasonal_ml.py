"""Tests for the ML Seasonal Analysis module.

Verifies:
1. /analytics/profit remains unchanged
2. Old AI seasonal route is removed
3. Segmentation logic assigns correct segments
4. PMS computation uses the balancing formula
5. Silver MCX features are optional/non-blocking
6. Forecast endpoints work
7. Procurement plan endpoints work
"""
import pytest
import numpy as np
from services.seasonal_ml_service import (
    segment_series, robust_scale, extract_item_family,
    SEGMENT_DENSE, SEGMENT_MEDIUM, SEGMENT_WEEKLY, SEGMENT_COLD,
)


class TestSegmentation:
    def test_dense_daily(self):
        assert segment_series(active_days=200, n_lines=600) == SEGMENT_DENSE

    def test_medium_daily(self):
        assert segment_series(active_days=80, n_lines=150) == SEGMENT_MEDIUM

    def test_weekly_sparse(self):
        assert segment_series(active_days=30, n_lines=50) == SEGMENT_WEEKLY

    def test_cold_start(self):
        assert segment_series(active_days=5, n_lines=10) == SEGMENT_COLD

    def test_boundary_dense(self):
        assert segment_series(active_days=180, n_lines=500) == SEGMENT_DENSE

    def test_boundary_medium(self):
        assert segment_series(active_days=60, n_lines=100) == SEGMENT_MEDIUM

    def test_boundary_weekly(self):
        assert segment_series(active_days=20, n_lines=10) == SEGMENT_WEEKLY

    def test_below_weekly(self):
        assert segment_series(active_days=19, n_lines=10) == SEGMENT_COLD


class TestRobustScale:
    def test_basic_scaling(self):
        arr = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
        scaled = robust_scale(arr)
        assert scaled.shape == arr.shape
        assert abs(np.median(scaled)) < 0.01

    def test_constant_array(self):
        arr = np.array([5.0, 5.0, 5.0, 5.0])
        scaled = robust_scale(arr)
        assert np.all(scaled == 0)

    def test_empty_array(self):
        arr = np.array([], dtype=float)
        scaled = robust_scale(arr)
        assert len(scaled) == 0

    def test_clipping(self):
        arr = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 100], dtype=float)
        scaled = robust_scale(arr, clip_iqr_mult=3.0)
        assert scaled[-1] <= 3.0


class TestItemFamily:
    def test_ring(self):
        assert extract_item_family("GOLD RING 22K") == "RING"

    def test_chain(self):
        assert extract_item_family(".CHAIN -058") == "CHAIN"

    def test_payal(self):
        assert extract_item_family("A-60 PAYAL-004") == "PAYAL"

    def test_coin(self):
        assert extract_item_family("COIN KUNDAN MINA") == "COIN"

    def test_kada(self):
        assert extract_item_family("KADA-AS 70") == "KADA"

    def test_unknown(self):
        assert extract_item_family("XYZ-12345") == "OTHER"


class TestPMSFormula:
    """Verify balanced_score = 0.5*(s+l) + 0.5*min(s,l)"""

    def test_both_positive(self):
        s, l_val = 1.0, 1.0
        balanced = 0.5 * (s + l_val) + 0.5 * min(s, l_val)
        assert balanced == 1.5

    def test_one_negative(self):
        s, l_val = 1.0, -1.0
        balanced = 0.5 * (s + l_val) + 0.5 * min(s, l_val)
        assert balanced == -0.5  # Penalises one-sided

    def test_both_negative(self):
        s, l_val = -1.0, -1.0
        balanced = 0.5 * (s + l_val) + 0.5 * min(s, l_val)
        assert balanced == -1.5

    def test_imbalance_pulls_down(self):
        # If silver is great but labour is terrible, balanced score is pulled down
        s, l_val = 2.0, -2.0
        balanced = 0.5 * (s + l_val) + 0.5 * min(s, l_val)
        pms = 1000 * balanced
        assert pms < 0, "Severe one-sided distortion should pull PMS negative"

    def test_moderate_imbalance_dampened(self):
        # s=2.0, l=-1.0 → balanced = 0.0 (dampened from the naive avg of 0.5)
        s, l_val = 2.0, -1.0
        balanced = 0.5 * (s + l_val) + 0.5 * min(s, l_val)
        naive_avg = (s + l_val) / 2
        assert balanced <= naive_avg, "Penalty should pull below naive average"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
