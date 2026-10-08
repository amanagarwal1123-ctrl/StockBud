"""Tests for daywise-comparisons CRUD and daily-sales inflation fix."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def sm_token():
    r = requests.post(f"{API}/auth/login", json={"username": "TEST_SM", "password": "sm123"}, timeout=30)
    if r.status_code != 200:
        pytest.skip("TEST_SM not available")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def sm_headers(sm_token):
    return {"Authorization": f"Bearer {sm_token}"}


# ---------- Daily-sales inflation fix ----------
class TestDailySalesInflationFix:
    def test_2024_02_01_excludes_historical(self, admin_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2024-02-01", "end_date": "2024-02-01"},
                         headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        daily = r.json()["daily_net_kg"]
        val = daily.get("2024-02-01", 0)
        assert abs(val - 0.882) < 0.01, f"Expected 0.882, got {val}"

    def test_2019_historical_only_preserved(self, admin_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2019-01-01", "end_date": "2019-12-31"},
                         headers=admin_headers, timeout=60)
        assert r.status_code == 200
        daily = r.json()["daily_net_kg"]
        assert abs(daily.get("2019-06-01", 0) - 1.5) < 0.01, f"2019-06-01 got {daily.get('2019-06-01')}"
        assert abs(daily.get("2019-06-02", 0) - 0.9) < 0.01, f"2019-06-02 got {daily.get('2019-06-02')}"

    def test_2025_year_sum_matches_sales_report(self, admin_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2025-01-01", "end_date": "2025-12-31"},
                         headers=admin_headers, timeout=120)
        assert r.status_code == 200
        s = sum(r.json()["daily_net_kg"].values())
        assert abs(s - 1060.153) < 0.1, f"2025 sum {s} != 1060.153"

    def test_2026_year_sum_matches_sales_report(self, admin_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2026-01-01", "end_date": "2026-12-31"},
                         headers=admin_headers, timeout=120)
        assert r.status_code == 200
        s = sum(r.json()["daily_net_kg"].values())
        assert abs(s - 3487.48) < 0.1, f"2026 sum {s} != 3487.48"


# ---------- Daywise comparisons CRUD ----------
class TestDaywiseComparisonsCRUD:
    created_ids = []

    def test_list_initial(self, admin_headers):
        r = requests.get(f"{API}/daywise-comparisons", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert "comparisons" in r.json()

    def test_create_auto_name(self, admin_headers):
        payload = {"entries": [
            {"anchor": "2026-02-12", "daysBack": 10},
            {"anchor": "2025-02-12", "daysBack": 10},
        ]}
        r = requests.post(f"{API}/daywise-comparisons", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["name"] == "2026 vs 2025"
        assert "id" in doc
        TestDaywiseComparisonsCRUD.created_ids.append(doc["id"])

        # Verify via GET
        g = requests.get(f"{API}/daywise-comparisons", headers=admin_headers, timeout=30)
        ids = [c["id"] for c in g.json()["comparisons"]]
        assert doc["id"] in ids

    def test_create_custom_name(self, admin_headers):
        payload = {"name": "TEST_Diwali", "entries": [{"anchor": "2026-02-12", "daysBack": 5}]}
        r = requests.post(f"{API}/daywise-comparisons", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_Diwali"
        TestDaywiseComparisonsCRUD.created_ids.append(r.json()["id"])

    def test_delete(self, admin_headers):
        payload = {"name": "TEST_todelete", "entries": [{"anchor": "2025-01-01", "daysBack": 3}]}
        r = requests.post(f"{API}/daywise-comparisons", json=payload, headers=admin_headers, timeout=30)
        cid = r.json()["id"]
        d = requests.delete(f"{API}/daywise-comparisons/{cid}", headers=admin_headers, timeout=30)
        assert d.status_code == 200

        # Verify absent
        g = requests.get(f"{API}/daywise-comparisons", headers=admin_headers, timeout=30)
        ids = [c["id"] for c in g.json()["comparisons"]]
        assert cid not in ids

    def test_delete_unknown_404(self, admin_headers):
        r = requests.delete(f"{API}/daywise-comparisons/non-existent-xyz", headers=admin_headers, timeout=30)
        assert r.status_code == 404

    def test_sm_forbidden(self, sm_headers):
        r = requests.get(f"{API}/daywise-comparisons", headers=sm_headers, timeout=30)
        assert r.status_code == 403
        r2 = requests.post(f"{API}/daywise-comparisons",
                           json={"entries": [{"anchor": "2025-01-01", "daysBack": 3}]},
                           headers=sm_headers, timeout=30)
        assert r2.status_code == 403

    def test_bad_anchor_400(self, admin_headers):
        r = requests.post(f"{API}/daywise-comparisons",
                          json={"entries": [{"anchor": "not-a-date", "daysBack": 5}]},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_days_back_too_large_400(self, admin_headers):
        r = requests.post(f"{API}/daywise-comparisons",
                          json={"entries": [{"anchor": "2025-01-01", "daysBack": 400}]},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_empty_entries_400(self, admin_headers):
        r = requests.post(f"{API}/daywise-comparisons", json={"entries": []},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_too_many_entries_400(self, admin_headers):
        entries = [{"anchor": f"202{i}-01-01", "daysBack": 3} for i in range(7)]
        r = requests.post(f"{API}/daywise-comparisons", json={"entries": entries},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_cleanup(self, admin_headers):
        """Delete any TEST_-prefixed or auto-named leftover comparisons."""
        g = requests.get(f"{API}/daywise-comparisons", headers=admin_headers, timeout=30)
        for c in g.json()["comparisons"]:
            requests.delete(f"{API}/daywise-comparisons/{c['id']}", headers=admin_headers, timeout=30)
        g2 = requests.get(f"{API}/daywise-comparisons", headers=admin_headers, timeout=30)
        assert g2.json()["comparisons"] == []
