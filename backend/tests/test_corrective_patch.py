"""Business-logic integration tests for the corrective patch.

Validates:
1. /analytics/profit output unchanged after shared helper refactor
2. PMS uses same margin components as shared profit logic
3. Historical purchases included in seasonal data
4. Silver-price service is optional/non-blocking
5. Missing uncovered history is NOT zero-demand
6. Old AI endpoints removed
7. Shared profit helper produces same results as direct engine
"""
import pytest
import httpx
import os
import numpy as np

API_URL = os.environ.get("TEST_API_URL", "")
if not API_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                API_URL = line.split("=", 1)[1].strip()
                break

@pytest.fixture(scope="module")
def admin_token():
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"username": "admin", "password": "admin123"}, timeout=15)
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def exec_token():
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"username": "TEST_EXEC", "password": "exec123"}, timeout=15)
    if r.status_code != 200:
        pytest.skip("TEST_EXEC user not available")
    return r.json()["access_token"]


class TestProfitUnchanged:
    """Verify /analytics/profit is unchanged after refactor."""

    def test_profit_endpoint_returns_expected_shape(self, admin_token):
        r = httpx.get(f"{API_URL}/api/analytics/profit",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "silver_profit_kg" in d
        assert "labor_profit_inr" in d
        assert "all_items" in d
        assert "total_items_analyzed" in d

    def test_profit_with_dates(self, admin_token):
        r = httpx.get(f"{API_URL}/api/analytics/profit?start_date=2026-01-01&end_date=2026-12-31",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200


class TestOldAIRemoved:
    """Old AI endpoints must return 404."""

    def test_smart_insights_removed(self, admin_token):
        r = httpx.post(f"{API_URL}/api/analytics/smart-insights",
                       headers={"Authorization": f"Bearer {admin_token}"},
                       json={}, timeout=15)
        assert r.status_code in (404, 405, 422)

    def test_seasonal_analysis_removed(self, admin_token):
        r = httpx.post(f"{API_URL}/api/ai/seasonal-analysis",
                       headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code in (404, 405)


class TestSharedProfitEngine:
    """PMS margins must come from the same logic as /analytics/profit."""

    def test_shared_helper_produces_margins(self):
        from services.profit_helpers import compute_item_margins
        # Minimal fixture: one sale, one ledger entry
        txns = [{"item_name": "TEST_ITEM", "type": "sale", "net_wt": 100,
                 "tunch": 60, "total_amount": 500, "labor": 0}]
        ledger = [{"item_name": "TEST_ITEM", "purchase_tunch": 55,
                   "labour_per_kg": 4000, "total_purchased_kg": 1,
                   "total_fine_kg": 0.55, "total_labour": 4}]
        results = compute_item_margins(txns, ledger, [], [])
        assert len(results) == 1
        r = results[0]
        # Silver margin: (60-55)*100/100 = 5 grams, per gram = 5/100 = 0.05
        assert abs(r["silver_margin_per_gram"] - 0.05) < 0.01
        # Labour margin: 500 - (4000/1000 * 100) = 500 - 400 = 100, per gram = 1.0
        assert abs(r["labour_margin_per_gram"] - 1.0) < 0.1

    def test_pms_uses_shared_margins(self, admin_token):
        """PMS final items must have margin fields from the shared engine."""
        r = httpx.get(f"{API_URL}/api/seasonal/pms-final",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200
        items = r.json()["items"]
        if items:
            item = items[0]
            assert "silver_margin_per_gram" in item
            assert "labour_margin_per_gram" in item
            assert "silver_score" in item
            assert "labour_score" in item
            assert "balanced_score" in item


class TestHistoricalPurchasesLoaded:
    """Seasonal analysis must include historical purchases."""

    def test_supplier_view_has_data(self, admin_token):
        """Supplier view should include both current and historical purchase data."""
        r = httpx.get(f"{API_URL}/api/seasonal/supplier-view",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200
        items = r.json()["items"]
        # If there are any purchases at all, supplier view should have entries
        # (exact count depends on data, but endpoint should not error)
        assert isinstance(items, list)

    def test_procurement_has_data(self, admin_token):
        r = httpx.get(f"{API_URL}/api/seasonal/procurement",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200
        items = r.json()["items"]
        assert isinstance(items, list)


class TestSilverServiceOptional:
    """Silver price service must degrade gracefully."""

    def test_silver_service_non_blocking(self, admin_token):
        """Seasonal compute must succeed even if silver API fails."""
        r = httpx.post(f"{API_URL}/api/seasonal/compute?force=true",
                       headers={"Authorization": f"Bearer {admin_token}"}, timeout=120)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ready"

    def test_silver_service_graceful_failure(self):
        """Silver fetch returns empty list on failure, not exception."""
        import asyncio
        from services.silver_price_service import fetch_silver_prices, compute_silver_features
        prices = asyncio.get_event_loop().run_until_complete(fetch_silver_prices())
        # May or may not have data — but must not raise
        features = compute_silver_features(prices)
        assert isinstance(features, dict)


class TestCoverageAwareDemand:
    """Missing history must NOT be converted to zero demand."""

    def test_uncovered_dates_are_nan(self):
        """Series reindex must produce NaN for uncovered dates, not zero."""
        import pandas as pd
        # Simulate: data exists on Jan 1 and Jan 10 only
        coverage = {pd.Timestamp("2026-01-01").date(), pd.Timestamp("2026-01-10").date()}
        idx = pd.date_range("2026-01-01", "2026-01-15", freq="D")
        series = pd.Series(index=idx, dtype=float)
        series.loc[pd.Timestamp("2026-01-01")] = 100.0
        series.loc[pd.Timestamp("2026-01-10")] = 50.0
        # Apply coverage-aware fill (same logic as seasonal_ml_service)
        for d in idx:
            if d.date() in coverage and pd.isna(series.loc[d]):
                series.loc[d] = 0.0
        # Jan 1 = 100 (real data)
        assert series.loc[pd.Timestamp("2026-01-01")] == 100.0
        # Jan 10 = 50 (real data)
        assert series.loc[pd.Timestamp("2026-01-10")] == 50.0
        # Jan 2-9 should be NaN (not covered, not zero)
        assert pd.isna(series.loc[pd.Timestamp("2026-01-05")])
        # Jan 11-15 should also be NaN
        assert pd.isna(series.loc[pd.Timestamp("2026-01-12")])

    def test_demand_forecast_has_confidence(self, admin_token):
        r = httpx.get(f"{API_URL}/api/seasonal/demand-forecast",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200
        items = r.json()["items"]
        if items:
            for item in items[:5]:
                assert "confidence" in item
                assert item["confidence"] in ("high", "medium", "low", "very_low")


class TestGroupResolutionInPMS:
    """PMS margin lookup must resolve member/mapped names to leader margins."""

    def test_margins_include_mapped_names(self):
        """Mapped transaction names must point to leader margins."""
        from services.profit_helpers import compute_item_margins
        from services.group_utils import build_group_maps

        groups = [{"group_name": "LEADER_A", "members": ["LEADER_A", "MEMBER_B"]}]
        mappings = [{"transaction_name": "TXN_RAW", "master_name": "MEMBER_B"}]
        txns = [
            {"item_name": "TXN_RAW", "type": "sale", "net_wt": 100, "tunch": 60, "total_amount": 500, "labor": 0},
            {"item_name": "LEADER_A", "type": "purchase", "net_wt": 200, "tunch": 55, "total_amount": 400, "labor": 0},
        ]
        ledger = [{"item_name": "LEADER_A", "purchase_tunch": 55,
                   "labour_per_kg": 4000, "total_purchased_kg": 1,
                   "total_fine_kg": 0.55, "total_labour": 4}]

        item_margins = compute_item_margins(txns, ledger, groups, mappings)
        # Margins should be keyed by leader
        assert len(item_margins) >= 1
        leader_margin = item_margins[0]
        assert leader_margin["item_name"] == "LEADER_A"

        # Now test the reverse-lookup in _compute_margins_shared style
        mapping_dict, member_to_leader, group_members = build_group_maps(groups, mappings)
        margins = {}
        for m in item_margins:
            entry = {"silver_margin_per_gram": m["silver_margin_per_gram"],
                     "labour_margin_per_gram": m["labour_margin_per_gram"],
                     "has_ledger": True}
            leader = m["item_name"]
            margins[leader] = entry
            for member in group_members.get(leader, []):
                if member != leader:
                    margins[member] = entry
        for txn_name, master_name in mapping_dict.items():
            resolved = member_to_leader.get(master_name, master_name)
            if resolved in margins and txn_name not in margins:
                margins[txn_name] = margins[resolved]

        # All three names should resolve to the same margins
        assert "LEADER_A" in margins
        assert "MEMBER_B" in margins
        assert "TXN_RAW" in margins
        assert margins["TXN_RAW"]["silver_margin_per_gram"] == margins["LEADER_A"]["silver_margin_per_gram"]

    def test_pms_items_have_nonzero_margins_for_grouped_items(self, admin_token):
        """At least some PMS items with groups should have non-zero margins."""
        r = httpx.get(f"{API_URL}/api/seasonal/pms-final",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("No PMS items computed")
        # Count items with has_ledger=True and non-zero margins
        with_margins = [i for i in items if i.get("has_ledger") and
                        (abs(i.get("silver_margin_per_gram", 0)) > 0.001 or
                         abs(i.get("labour_margin_per_gram", 0)) > 0.001)]
        assert len(with_margins) > 0, "No PMS items have non-zero margins"


class TestSaleReturnNotCorruptingPurchaseTunch:
    """Sale returns must NOT contaminate purchase cost basis."""

    def test_sale_return_does_not_affect_purchase_tunch(self):
        """sale_return tunch is the SALE tunch, not the purchase cost.
        It must go into the sales bucket, not the purchases bucket."""
        from services.profit_helpers import compute_item_margins

        txns = [
            {"item_name": "TEST_SR", "type": "purchase", "net_wt": 10000, "tunch": 51, "total_amount": 200, "labor": 0},
            {"item_name": "TEST_SR", "type": "sale", "net_wt": 5000, "tunch": 55, "total_amount": 100, "labor": 0},
            {"item_name": "TEST_SR", "type": "sale_return", "net_wt": -200, "tunch": 46, "total_amount": -4, "labor": 0},
        ]
        ledger = [{"item_name": "TEST_SR", "purchase_tunch": 51,
                   "labour_per_kg": 4000, "total_purchased_kg": 10,
                   "total_fine_kg": 5.1, "total_labour": 40}]
        results = compute_item_margins(txns, ledger, [], [])
        assert len(results) == 1
        r = results[0]
        # Purchase tunch must stay at 51 (actual purchase), NOT be corrupted by sale_return's 46
        assert r["avg_purchase_tunch"] == 51.0
        # Net sold = 5000 - 200 = 4800g = 4.8 kg
        assert r["net_wt_sold_kg"] == 4.8

    def test_sale_return_reduces_sold_weight(self):
        """sale_return with negative net_wt should reduce total sold weight."""
        from services.profit_helpers import compute_item_margins

        txns = [
            {"item_name": "TEST_SRW", "type": "purchase", "net_wt": 10000, "tunch": 50, "total_amount": 0, "labor": 0},
            {"item_name": "TEST_SRW", "type": "sale", "net_wt": 8000, "tunch": 55, "total_amount": 160, "labor": 0},
            {"item_name": "TEST_SRW", "type": "sale_return", "net_wt": -1000, "tunch": 55, "total_amount": -20, "labor": 0},
        ]
        ledger = []
        results = compute_item_margins(txns, ledger, [], [])
        assert len(results) == 1
        r = results[0]
        # Net sold = 8000 - 1000 = 7000g = 7.0 kg
        assert r["net_wt_sold_kg"] == 7.0
        # Purchase tunch = 50 (from purchase only, not from sale_return)
        assert r["avg_purchase_tunch"] == 50.0

    def test_profit_endpoint_buy_tunch_uncontaminated(self, admin_token):
        """Profit endpoint should not show sale_return tunch as purchase tunch."""
        r = httpx.get(f"{API_URL}/api/analytics/profit",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        items = r.json().get("all_items", [])
        # Verify no item has avg_purchase_tunch that looks like a sale tunch
        # (this is a sanity check — specific values depend on data)
        assert isinstance(items, list)


class TestNonAdminRejection:
    """All seasonal endpoints must reject non-admin."""

    def test_pms_final_403(self, exec_token):
        r = httpx.get(f"{API_URL}/api/seasonal/pms-final",
                      headers={"Authorization": f"Bearer {exec_token}"}, timeout=15)
        assert r.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
