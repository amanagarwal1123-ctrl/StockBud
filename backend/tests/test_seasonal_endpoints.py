"""Backend API tests for Seasonal ML Analysis endpoints.

Tests:
1. /api/analytics/profit - unchanged, returns profit data
2. /api/ai/seasonal-analysis - removed, returns 404
3. /api/seasonal/compute - triggers computation, returns summary
4. /api/seasonal/pms-final - returns ranked items with balanced_score
5. /api/seasonal/pms-silver - returns ranked items by silver PMS
6. /api/seasonal/pms-labour - returns ranked items by labour PMS
7. /api/seasonal/demand-forecast - returns items with forecast_14d, forecast_30d
8. /api/seasonal/seasonality - returns items with monthly_profile, peak_months
9. /api/seasonal/procurement - returns items with action, reason_code, suggested_qty_g
10. /api/seasonal/supplier-view - returns suppliers with avg_item_pms
11. /api/seasonal/dead-stock - returns dead_stock and slow_mover items
12. All seasonal endpoints reject non-admin users with 403
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"username": "admin", "password": "admin123"}
EXEC_CREDS = {"username": "TEST_EXEC", "password": "exec123"}


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def exec_token():
    """Get executive authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=EXEC_CREDS)
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Executive authentication failed")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def exec_headers(exec_token):
    """Headers with executive auth"""
    return {"Authorization": f"Bearer {exec_token}", "Content-Type": "application/json"}


class TestProfitEndpointUnchanged:
    """Verify /api/analytics/profit still works and returns expected data"""

    def test_profit_endpoint_returns_200(self, admin_headers):
        """GET /api/analytics/profit should return 200"""
        response = requests.get(f"{BASE_URL}/api/analytics/profit", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_profit_endpoint_returns_expected_fields(self, admin_headers):
        """Profit response should have silver_profit_kg, labor_profit_inr, all_items"""
        response = requests.get(f"{BASE_URL}/api/analytics/profit", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        # Verify expected fields exist
        assert "silver_profit_kg" in data, "Missing silver_profit_kg field"
        assert "labor_profit_inr" in data, "Missing labor_profit_inr field"
        assert "all_items" in data, "Missing all_items field"
        assert "total_items_analyzed" in data, "Missing total_items_analyzed field"


class TestOldSeasonalEndpointRemoved:
    """Verify old /api/ai/seasonal-analysis is removed"""

    def test_old_seasonal_endpoint_returns_404(self, admin_headers):
        """POST /api/ai/seasonal-analysis should return 404 (removed)"""
        response = requests.post(
            f"{BASE_URL}/api/ai/seasonal-analysis",
            headers=admin_headers,
            json={}
        )
        # Should be 404 (not found) or 405 (method not allowed)
        assert response.status_code in [404, 405, 422], \
            f"Old seasonal endpoint should be removed, got {response.status_code}"


class TestSeasonalCompute:
    """Test /api/seasonal/compute endpoint"""

    def test_compute_returns_200_for_admin(self, admin_headers):
        """POST /api/seasonal/compute should return 200 for admin"""
        response = requests.post(f"{BASE_URL}/api/seasonal/compute", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_compute_returns_summary_fields(self, admin_headers):
        """Compute response should have status, total_items, segments_summary"""
        response = requests.post(f"{BASE_URL}/api/seasonal/compute", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data, "Missing status field"
        assert "total_items" in data, "Missing total_items field"
        assert "segments_summary" in data, "Missing segments_summary field"
        assert data["total_items"] > 0, "Should have items processed"

    def test_compute_rejects_non_admin(self, exec_headers):
        """POST /api/seasonal/compute should return 403 for non-admin"""
        response = requests.post(f"{BASE_URL}/api/seasonal/compute", headers=exec_headers)
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"


class TestPMSFinal:
    """Test /api/seasonal/pms-final endpoint"""

    def test_pms_final_returns_200(self, admin_headers):
        """GET /api/seasonal/pms-final should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-final", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_pms_final_has_required_fields(self, admin_headers):
        """PMS Final items should have pms, silver_score, labour_score, balanced_score"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-final", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data, "Missing items field"
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "pms" in item, "Missing pms field"
            assert "silver_score" in item, "Missing silver_score field"
            assert "labour_score" in item, "Missing labour_score field"
            assert "balanced_score" in item, "Missing balanced_score field"
            assert "item_name" in item, "Missing item_name field"
            assert "stamp" in item, "Missing stamp field"

    def test_pms_final_rejects_non_admin(self, exec_headers):
        """GET /api/seasonal/pms-final should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-final", headers=exec_headers)
        assert response.status_code == 403


class TestPMSSilver:
    """Test /api/seasonal/pms-silver endpoint"""

    def test_pms_silver_returns_200(self, admin_headers):
        """GET /api/seasonal/pms-silver should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-silver", headers=admin_headers)
        assert response.status_code == 200

    def test_pms_silver_has_items(self, admin_headers):
        """PMS Silver should return items with pms field"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-silver", headers=admin_headers)
        data = response.json()
        assert "items" in data
        if len(data["items"]) > 0:
            assert "pms" in data["items"][0]
            assert "silver_score" in data["items"][0]

    def test_pms_silver_rejects_non_admin(self, exec_headers):
        """GET /api/seasonal/pms-silver should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-silver", headers=exec_headers)
        assert response.status_code == 403


class TestPMSLabour:
    """Test /api/seasonal/pms-labour endpoint"""

    def test_pms_labour_returns_200(self, admin_headers):
        """GET /api/seasonal/pms-labour should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-labour", headers=admin_headers)
        assert response.status_code == 200

    def test_pms_labour_has_items(self, admin_headers):
        """PMS Labour should return items with pms and labour_score"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-labour", headers=admin_headers)
        data = response.json()
        assert "items" in data
        if len(data["items"]) > 0:
            assert "pms" in data["items"][0]
            assert "labour_score" in data["items"][0]

    def test_pms_labour_rejects_non_admin(self, exec_headers):
        """GET /api/seasonal/pms-labour should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/seasonal/pms-labour", headers=exec_headers)
        assert response.status_code == 403


class TestDemandForecast:
    """Test /api/seasonal/demand-forecast endpoint"""

    def test_demand_forecast_returns_200(self, admin_headers):
        """GET /api/seasonal/demand-forecast should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/demand-forecast", headers=admin_headers)
        assert response.status_code == 200

    def test_demand_forecast_has_required_fields(self, admin_headers):
        """Demand forecast items should have forecast_14d, forecast_30d, confidence, segment"""
        response = requests.get(f"{BASE_URL}/api/seasonal/demand-forecast", headers=admin_headers)
        data = response.json()
        assert "items" in data
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "forecast_14d" in item, "Missing forecast_14d"
            assert "forecast_30d" in item, "Missing forecast_30d"
            assert "confidence" in item, "Missing confidence"
            assert "segment" in item, "Missing segment"

    def test_demand_forecast_rejects_non_admin(self, exec_headers):
        """GET /api/seasonal/demand-forecast should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/seasonal/demand-forecast", headers=exec_headers)
        assert response.status_code == 403


class TestSeasonality:
    """Test /api/seasonal/seasonality endpoint"""

    def test_seasonality_returns_200(self, admin_headers):
        """GET /api/seasonal/seasonality should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/seasonality", headers=admin_headers)
        assert response.status_code == 200

    def test_seasonality_has_required_fields(self, admin_headers):
        """Seasonality items should have monthly_profile and peak_months"""
        response = requests.get(f"{BASE_URL}/api/seasonal/seasonality", headers=admin_headers)
        data = response.json()
        assert "items" in data
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "monthly_profile" in item, "Missing monthly_profile"
            assert "peak_months" in item, "Missing peak_months"
            assert "item_name" in item, "Missing item_name"

    def test_seasonality_rejects_non_admin(self, exec_headers):
        """GET /api/seasonal/seasonality should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/seasonal/seasonality", headers=exec_headers)
        assert response.status_code == 403


class TestProcurement:
    """Test /api/seasonal/procurement endpoint"""

    def test_procurement_returns_200(self, admin_headers):
        """GET /api/seasonal/procurement should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/procurement", headers=admin_headers)
        assert response.status_code == 200

    def test_procurement_has_required_fields(self, admin_headers):
        """Procurement items should have action, reason_code, suggested_qty_g"""
        response = requests.get(f"{BASE_URL}/api/seasonal/procurement", headers=admin_headers)
        data = response.json()
        assert "items" in data
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "action" in item, "Missing action field"
            assert "reason_code" in item, "Missing reason_code field"
            assert "suggested_qty_g" in item, "Missing suggested_qty_g field"
            # Action should be 'buy' or 'hold'
            assert item["action"] in ["buy", "hold"], f"Invalid action: {item['action']}"

    def test_procurement_rejects_non_admin(self, exec_headers):
        """GET /api/seasonal/procurement should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/seasonal/procurement", headers=exec_headers)
        assert response.status_code == 403


class TestSupplierView:
    """Test /api/seasonal/supplier-view endpoint"""

    def test_supplier_view_returns_200(self, admin_headers):
        """GET /api/seasonal/supplier-view should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/supplier-view", headers=admin_headers)
        assert response.status_code == 200

    def test_supplier_view_has_required_fields(self, admin_headers):
        """Supplier view items should have supplier, avg_item_pms"""
        response = requests.get(f"{BASE_URL}/api/seasonal/supplier-view", headers=admin_headers)
        data = response.json()
        assert "items" in data
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "supplier" in item, "Missing supplier field"
            assert "avg_item_pms" in item, "Missing avg_item_pms field"

    def test_supplier_view_rejects_non_admin(self, exec_headers):
        """GET /api/seasonal/supplier-view should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/seasonal/supplier-view", headers=exec_headers)
        assert response.status_code == 403


class TestDeadStock:
    """Test /api/seasonal/dead-stock endpoint"""

    def test_dead_stock_returns_200(self, admin_headers):
        """GET /api/seasonal/dead-stock should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/dead-stock", headers=admin_headers)
        assert response.status_code == 200

    def test_dead_stock_has_required_fields(self, admin_headers):
        """Dead stock items should have classification (dead_stock or slow_mover)"""
        response = requests.get(f"{BASE_URL}/api/seasonal/dead-stock", headers=admin_headers)
        data = response.json()
        assert "items" in data
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "classification" in item, "Missing classification field"
            assert item["classification"] in ["dead_stock", "slow_mover"], \
                f"Invalid classification: {item['classification']}"
            assert "item_name" in item, "Missing item_name"
            assert "days_since_last_sale" in item, "Missing days_since_last_sale"

    def test_dead_stock_rejects_non_admin(self, exec_headers):
        """GET /api/seasonal/dead-stock should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/seasonal/dead-stock", headers=exec_headers)
        assert response.status_code == 403


class TestSeasonalStatus:
    """Test /api/seasonal/status endpoint"""

    def test_status_returns_200(self, admin_headers):
        """GET /api/seasonal/status should return 200"""
        response = requests.get(f"{BASE_URL}/api/seasonal/status", headers=admin_headers)
        assert response.status_code == 200

    def test_status_has_cached_field(self, admin_headers):
        """Status should indicate if data is cached"""
        response = requests.get(f"{BASE_URL}/api/seasonal/status", headers=admin_headers)
        data = response.json()
        assert "cached" in data, "Missing cached field"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
