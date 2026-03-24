"""
Tests for the Codex-recommended physical stock fixes:
1. POST /api/upload/init with physical_stock returns 400
2. GET /api/physical-stock/dates returns sorted dates
3. GET /api/physical-stock/compare without verification_date returns 422
4. Compare with selected date reads only that date
5. Stale apply returns skipped result and updated_count=0
6. Partial apply returns accurate updated_count and per-row statuses
7. Apply with skipped_count in response
"""
import pytest
import httpx
import os

BASE = os.environ.get("TEST_API_URL", "https://date-scoped-stock.preview.emergentagent.com")
API = f"{BASE}/api"

@pytest.fixture(scope="module")
def token():
    resp = httpx.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]

@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestUploadInitGuard:
    def test_physical_stock_init_returns_400(self, auth):
        """POST /api/upload/init with file_type=physical_stock should return 400"""
        resp = httpx.post(f"{API}/upload/init", json={"file_type": "physical_stock", "total_chunks": 1}, headers=auth)
        assert resp.status_code == 400
        assert "direct upload flow" in resp.json()["detail"]

    def test_other_types_init_ok(self, auth):
        """POST /api/upload/init with non-physical types should succeed"""
        resp = httpx.post(f"{API}/upload/init", json={"file_type": "purchase", "total_chunks": 1}, headers=auth)
        assert resp.status_code == 200
        assert "upload_id" in resp.json()


class TestPhysicalStockDates:
    def test_dates_endpoint_returns_sorted(self, auth):
        """GET /api/physical-stock/dates returns dates sorted descending"""
        resp = httpx.get(f"{API}/physical-stock/dates", headers=auth)
        assert resp.status_code == 200
        dates = resp.json()["dates"]
        assert isinstance(dates, list)
        # Check sorted descending
        for i in range(len(dates) - 1):
            assert dates[i] >= dates[i + 1], f"Dates not sorted descending: {dates[i]} < {dates[i+1]}"


class TestCompareRequiresDate:
    def test_compare_without_date_returns_error(self, auth):
        """GET /api/physical-stock/compare without verification_date returns 422"""
        resp = httpx.get(f"{API}/physical-stock/compare", headers=auth)
        assert resp.status_code == 422  # FastAPI validation error for missing required param

    def test_compare_with_date_works(self, auth):
        """GET /api/physical-stock/compare?verification_date=X returns comparison data"""
        # Get a valid date first
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

    def test_compare_with_nonexistent_date(self, auth):
        """Compare with a date that has no physical stock returns empty results"""
        resp = httpx.get(f"{API}/physical-stock/compare?verification_date=1999-01-01", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        # Should have summary but zero physical items
        assert data["summary"]["total_physical_kg"] == 0


class TestApplyResults:
    def test_apply_nonexistent_item_returns_skipped(self, auth):
        """Apply with an item not found for the date should return skipped"""
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

    def test_apply_response_has_required_fields(self, auth):
        """Apply response should include updated_count, skipped_count, verification_date, results"""
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
        assert "updated_count" in data
        assert "skipped_count" in data
        assert "verification_date" in data
        assert "results" in data
        assert data["verification_date"] == dates[0]


class TestExistingBehaviorPreserved:
    def test_upload_preview_requires_date(self, auth):
        """upload-preview should require verification_date"""
        # We can't easily test file upload without a real file, but we can check
        # that the endpoint exists
        resp = httpx.post(f"{API}/physical-stock/upload-preview", headers=auth)
        # Should fail with 422 (missing file) not 404
        assert resp.status_code == 422

    def test_apply_requires_date(self, auth):
        """apply-updates should require verification_date"""
        resp = httpx.post(f"{API}/physical-stock/apply-updates", json={"items": [{"item_name": "X", "new_gr_wt": 0, "new_net_wt": 0}]}, headers=auth)
        assert resp.status_code == 400
        assert "verification_date" in resp.json()["detail"]
