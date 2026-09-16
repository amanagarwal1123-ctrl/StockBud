"""Integration tests for iteration 52: heavy queue, cache, streaming refactor.
Covers sales-report, monthly-profit, sales-reconciliation, concurrent burst,
sales-manager-report regression.
"""
import os
import time
import concurrent.futures
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stock-vs-sales.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {username}: {r.status_code} {r.text[:200]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin', 'admin123')}"}


@pytest.fixture(scope="module")
def sm_headers():
    return {"Authorization": f"Bearer {_login('TEST_SM', 'sm123')}"}


# ---------- sales-report cache + shape ----------
def test_sales_report_2025_all_returns_200_and_shape(admin_headers):
    r = requests.get(f"{API}/analytics/sales-report", params={"year": 2025, "month": 0}, headers=admin_headers, timeout=90)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    for k in ("by_stamp", "by_item", "totals"):
        assert k in body, f"missing key {k}"
    if body["by_item"]:
        row = body["by_item"][0]
        for f in ("stock_sale_ratio", "avg_stock_kg", "merged_names"):
            assert f in row, f"by_item row missing {f}: keys={list(row.keys())}"


def test_sales_report_cache_hit_identical(admin_headers):
    p = {"year": 2025, "month": 0}
    r1 = requests.get(f"{API}/analytics/sales-report", params=p, headers=admin_headers, timeout=90)
    t0 = time.time()
    r2 = requests.get(f"{API}/analytics/sales-report", params=p, headers=admin_headers, timeout=90)
    dt2 = time.time() - t0
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json(), "cache hit should return identical payload"
    print(f"cache hit call took {dt2:.3f}s")


# ---------- monthly-profit streaming ----------
def test_monthly_profit_2025_all(admin_headers):
    r = requests.get(f"{API}/analytics/monthly-profit", params={"year": 2025, "month": 0}, headers=admin_headers, timeout=90)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    # endpoint returns 'all_items' + 'total_net_wt_sold' (streaming refactor)
    assert "all_items" in body or "items" in body, f"missing items key: {list(body.keys())}"
    assert "total_net_wt_sold" in body
    assert body["total_net_wt_sold"] is not None


# ---------- sales-reconciliation streaming ----------
def test_sales_reconciliation_2025(admin_headers):
    r = requests.get(f"{API}/analytics/sales-reconciliation",
                     params={"start_date": "2025-01-01", "end_date": "2025-12-31"},
                     headers=admin_headers, timeout=90)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "rows" in body or "items" in body or isinstance(body, dict)
    # accept totals-like keys
    assert any(k in body for k in ("totals", "total", "summary", "grand_totals_all_items")), f"no totals-like key: {list(body.keys())}"


# ---------- concurrent burst ----------
def test_concurrent_heavy_burst_no_crash(admin_headers):
    # pick an item name for drill (best effort)
    item_name = "ANYITEM"
    try:
        rr = requests.get(f"{API}/analytics/sales-report", params={"year": 2025, "month": 0}, headers=admin_headers, timeout=60)
        if rr.status_code == 200 and rr.json().get("by_item"):
            item_name = rr.json()["by_item"][0].get("merged_names") or rr.json()["by_item"][0].get("name") or item_name
            if isinstance(item_name, list):
                item_name = item_name[0]
    except Exception:
        pass

    urls = [
        (f"{API}/analytics/sales-report", {"year": 2025, "month": 0}),
        (f"{API}/analytics/sales-report", {"year": 2024, "month": 0}),
        (f"{API}/analytics/monthly-profit", {"year": 2025, "month": 0}),
        (f"{API}/analytics/visualization", {"start_date": "2025-01-01", "end_date": "2025-12-31"}),
        (f"{API}/analytics/profit", {"start_date": "2025-01-01", "end_date": "2025-12-31"}),
        (f"{API}/analytics/customer-profit", {}),
        (f"{API}/analytics/sales-reconciliation", {"start_date": "2025-01-01", "end_date": "2025-12-31"}),
        (f"{API}/purchase-list", {}),
        (f"{API}/analytics/sales-report-drill", {"entity_type": "item", "name": item_name, "start_date": "2025-01-01", "end_date": "2025-12-31"}),
        (f"{API}/analytics/monthly-profit", {"year": 2024, "month": 0}),
    ]

    def fire(u):
        url, params = u
        try:
            resp = requests.get(url, params=params, headers=admin_headers, timeout=120)
            return (url, resp.status_code, resp.text[:200] if resp.status_code >= 400 else "")
        except Exception as e:
            return (url, "ERR", str(e)[:200])

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls)) as ex:
        results = list(ex.map(fire, urls))

    failures = [r for r in results if r[1] != 200]
    print(f"Burst results: {results}")
    assert not failures, f"non-200 in burst: {failures}"

    # server alive?
    alive = requests.get(f"{API}/stats", headers=admin_headers, timeout=30)
    assert alive.status_code == 200, f"/api/stats down after burst: {alive.status_code} {alive.text[:200]}"


# ---------- sales-manager-report regression ----------
def test_sales_manager_report_regression(sm_headers):
    # last ~30 days window
    from datetime import date, timedelta
    end = date.today()
    start = end - timedelta(days=45)
    r = requests.get(f"{API}/analytics/sales-manager-report",
                     params={"start_date": start.isoformat(), "end_date": end.isoformat()},
                     headers=sm_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
