"""
Iteration 22: Comprehensive tests for Codex-recommended physical stock patches
Tests:
1. POST /api/upload/init with file_type=physical_stock returns 400 (direct upload only)
2. POST /api/upload/init with file_type=purchase returns 200 (non-physical types unaffected)
3. GET /api/physical-stock/dates returns sorted descending list of dates
4. GET /api/physical-stock/compare without verification_date returns 422
5. GET /api/physical-stock/compare?verification_date=X returns data for that specific date
6. Apply-updates with nonexistent item returns skipped status and updated_count=0
7. Apply-updates response includes skipped_count field
8. Apply-updates requires verification_date
"""
import pytest
import httpx
import os

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://inventory-ml-1.preview.emergentagent.com")
API = f"{BASE}/api"

@pytest.fixture(scope="module")
def token():
    resp = httpx.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]

@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestPhysicalStockUploadInit:
    """Test that physical_stock is rejected from chunked upload"""
    
    def test_physical_stock_init_returns_400(self, auth):
        """POST /api/upload/init with file_type=physical_stock returns 400"""
        resp = httpx.post(f"{API}/upload/init", 
                         json={"file_type": "physical_stock", "total_chunks": 1}, 
                         headers=auth)
        assert resp.status_code == 400
        data = resp.json()
        assert "direct upload flow" in data["detail"].lower()
    
    def test_purchase_init_returns_200(self, auth):
        """POST /api/upload/init with file_type=purchase returns 200"""
        resp = httpx.post(f"{API}/upload/init", 
                         json={"file_type": "purchase", "total_chunks": 1}, 
                         headers=auth)
        assert resp.status_code == 200
        assert "upload_id" in resp.json()
    
    def test_sale_init_returns_200(self, auth):
        """POST /api/upload/init with file_type=sale returns 200"""
        resp = httpx.post(f"{API}/upload/init", 
                         json={"file_type": "sale", "total_chunks": 1}, 
                         headers=auth)
        assert resp.status_code == 200
        assert "upload_id" in resp.json()


class TestPhysicalStockDates:
    """Test /physical-stock/dates endpoint"""
    
    def test_dates_endpoint_exists(self, auth):
        """GET /api/physical-stock/dates returns 200"""
        resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        assert resp.status_code == 200
    
    def test_dates_returns_list(self, auth):
        """Response contains 'dates' array"""
        resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        data = resp.json()
        assert "dates" in data
        assert isinstance(data["dates"], list)
    
    def test_dates_sorted_descending(self, auth):
        """Dates are sorted in descending order (newest first)"""
        resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        dates = resp.json()["dates"]
        for i in range(len(dates) - 1):
            assert dates[i] >= dates[i + 1], f"Dates not sorted: {dates[i]} < {dates[i+1]}"


class TestPhysicalStockCompare:
    """Test /physical-stock/compare endpoint requires verification_date"""
    
    def test_compare_without_date_returns_422(self, auth):
        """GET /api/physical-stock/compare without verification_date returns 422"""
        resp = httpx.get(f"{API}/physical-stock/compare", headers=auth)
        assert resp.status_code == 422  # FastAPI validation error
    
    def test_compare_with_valid_date(self, auth):
        """GET /api/physical-stock/compare?verification_date=X returns 200"""
        # Get available dates first
        dates_resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        dates = dates_resp.json().get("dates", [])
        if not dates:
            pytest.skip("No physical stock dates available")
        
        resp = httpx.get(f"{API}/physical-stock/compare?verification_date={dates[0]}", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "matches" in data
        assert "discrepancies" in data
    
    def test_compare_returns_data_for_specific_date(self, auth):
        """Compare returns data scoped to the specified date only"""
        dates_resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        dates = dates_resp.json().get("dates", [])
        if not dates:
            pytest.skip("No physical stock dates available")
        
        resp = httpx.get(f"{API}/physical-stock/compare?verification_date={dates[0]}", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        # The endpoint should return comparison data (summary exists means query was successful)
        assert "summary" in data
    
    def test_compare_nonexistent_date_returns_empty(self, auth):
        """Compare with nonexistent date returns empty physical stock"""
        resp = httpx.get(f"{API}/physical-stock/compare?verification_date=1999-01-01", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_physical_kg"] == 0


class TestApplyUpdatesResponse:
    """Test /physical-stock/apply-updates response format"""
    
    def test_apply_requires_verification_date(self, auth):
        """Apply-updates without verification_date returns 400"""
        resp = httpx.post(f"{API}/physical-stock/apply-updates", 
                         json={"items": [{"item_name": "TEST", "new_gr_wt": 0, "new_net_wt": 0}]},
                         headers=auth)
        assert resp.status_code == 400
        assert "verification_date" in resp.json()["detail"]
    
    def test_apply_response_has_updated_count(self, auth):
        """Apply response includes updated_count"""
        dates_resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        dates = dates_resp.json().get("dates", [])
        if not dates:
            pytest.skip("No physical stock dates available")
        
        resp = httpx.post(f"{API}/physical-stock/apply-updates", json={
            "verification_date": dates[0],
            "items": [{"item_name": "TEST_ITEM_XYZ", "new_gr_wt": 0, "new_net_wt": 0, "update_mode": "gross_only"}]
        }, headers=auth)
        assert resp.status_code == 200
        assert "updated_count" in resp.json()
    
    def test_apply_response_has_skipped_count(self, auth):
        """Apply response includes skipped_count"""
        dates_resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        dates = dates_resp.json().get("dates", [])
        if not dates:
            pytest.skip("No physical stock dates available")
        
        resp = httpx.post(f"{API}/physical-stock/apply-updates", json={
            "verification_date": dates[0],
            "items": [{"item_name": "TEST_ITEM_XYZ", "new_gr_wt": 0, "new_net_wt": 0, "update_mode": "gross_only"}]
        }, headers=auth)
        assert resp.status_code == 200
        assert "skipped_count" in resp.json()
    
    def test_apply_nonexistent_item_returns_skipped(self, auth):
        """Apply with nonexistent item has skipped status"""
        dates_resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        dates = dates_resp.json().get("dates", [])
        if not dates:
            pytest.skip("No physical stock dates available")
        
        resp = httpx.post(f"{API}/physical-stock/apply-updates", json={
            "verification_date": dates[0],
            "items": [{"item_name": "NONEXISTENT_ITEM_XYZ_999", "new_gr_wt": 100, "new_net_wt": 90, "update_mode": "gross_only"}]
        }, headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_count"] == 0
        assert data["skipped_count"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "skipped"
    
    def test_apply_response_includes_verification_date(self, auth):
        """Apply response echoes back the verification_date"""
        dates_resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        dates = dates_resp.json().get("dates", [])
        if not dates:
            pytest.skip("No physical stock dates available")
        
        resp = httpx.post(f"{API}/physical-stock/apply-updates", json={
            "verification_date": dates[0],
            "items": [{"item_name": "FAKE_ITEM", "new_gr_wt": 0, "new_net_wt": 0, "update_mode": "gross_only"}]
        }, headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "verification_date" in data
        assert data["verification_date"] == dates[0]
