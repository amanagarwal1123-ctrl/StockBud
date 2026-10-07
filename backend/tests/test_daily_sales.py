"""Tests for /api/analytics/daily-sales (Compare Sales Daywise feature)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {username}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin', 'admin123')}"}


@pytest.fixture(scope="module")
def sm_headers():
    try:
        return {"Authorization": f"Bearer {_login('TEST_SM', 'sm123')}"}
    except AssertionError:
        pytest.skip("TEST_SM not available")


class TestDailySales:
    def test_admin_fetch_range(self, admin_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2026-02-08", "end_date": "2026-02-12"},
                         headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "daily_net_kg" in data
        assert data["start_date"] == "2026-02-08"
        assert data["end_date"] == "2026-02-12"
        # Regression: 2026-02-10 must equal 93.539
        assert data["daily_net_kg"].get("2026-02-10") == 93.539, data["daily_net_kg"]

    def test_cached_identical(self, admin_headers):
        r1 = requests.get(f"{API}/analytics/daily-sales",
                          params={"start_date": "2026-02-08", "end_date": "2026-02-12"},
                          headers=admin_headers, timeout=60)
        r2 = requests.get(f"{API}/analytics/daily-sales",
                          params={"start_date": "2026-02-08", "end_date": "2026-02-12"},
                          headers=admin_headers, timeout=60)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()

    def test_non_admin_forbidden(self, sm_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2026-02-08", "end_date": "2026-02-12"},
                         headers=sm_headers, timeout=30)
        assert r.status_code == 403

    def test_start_after_end(self, admin_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2026-02-12", "end_date": "2026-02-08"},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_range_too_large(self, admin_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2024-01-01", "end_date": "2025-12-31"},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_bad_date_format(self, admin_headers):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "not-a-date", "end_date": "also-bad"},
                         headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_no_auth(self):
        r = requests.get(f"{API}/analytics/daily-sales",
                         params={"start_date": "2026-02-08", "end_date": "2026-02-12"},
                         timeout=30)
        assert r.status_code in (401, 403)
