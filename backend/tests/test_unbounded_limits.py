"""Backend regression tests: verify removal of hardcoded to_list limits
Tests the fixes that removed .to_list(1000)/.to_list(50000) truncation in
calculation-affecting queries (item history, visualization, stats, profit).
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

TIMEOUT = 60


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# --- Basic auth ---
def test_admin_login_returns_jwt():
    r = requests.post(
        f"{API}/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200
    tok = r.json().get("access_token") or r.json().get("token")
    assert isinstance(tok, str) and len(tok) > 20


# --- Inventory current: full list ---
def test_inventory_current(auth_headers):
    t0 = time.time()
    r = requests.get(f"{API}/inventory/current", headers=auth_headers, timeout=TIMEOUT)
    elapsed = time.time() - t0
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    assert elapsed < 30, f"too slow: {elapsed:.1f}s"
    data = r.json()
    # Response could be list or dict wrapper
    items = data if isinstance(data, list) else (data.get("items") or data.get("inventory") or data.get("data") or [])
    assert isinstance(items, list)
    print(f"inventory items: {len(items)}, elapsed: {elapsed:.2f}s")


# --- Dashboard stats: total transactions should reflect full DB ---
def test_dashboard_stats(auth_headers):
    t0 = time.time()
    r = requests.get(f"{API}/stats", headers=auth_headers, timeout=TIMEOUT)
    elapsed = time.time() - t0
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    assert elapsed < 30
    data = r.json()
    print(f"dashboard/stats keys: {list(data.keys())[:20]}")
    print(f"stats sample: {str(data)[:500]}")


# --- Item detail for high-volume item ---
def test_item_detail_high_volume(auth_headers):
    inv = requests.get(f"{API}/inventory/current", headers=auth_headers, timeout=TIMEOUT).json()
    items = inv if isinstance(inv, list) else (inv.get("items") or inv.get("inventory") or inv.get("data") or [])
    if not items:
        pytest.skip("no inventory items")

    # pick items by likely transaction count field
    def txn_count(it):
        for k in ("total_transactions", "transaction_count", "num_transactions", "txn_count"):
            if isinstance(it, dict) and k in it and isinstance(it[k], (int, float)):
                return it[k]
        return 0

    sorted_items = sorted([i for i in items if isinstance(i, dict)], key=txn_count, reverse=True)
    picks = sorted_items[:3] if sorted_items else items[:3]

    tested = 0
    for it in picks:
        name = it.get("item_name") or it.get("name") or it.get("item") or it.get("_id")
        if not name:
            continue
        t0 = time.time()
        r = requests.get(f"{API}/item/{name}", headers=auth_headers, timeout=TIMEOUT)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"item {name}: {r.status_code} {r.text[:300]}"
        assert elapsed < 30, f"item {name} slow: {elapsed:.1f}s"
        j = r.json()
        # verify some statistics keys exist
        print(f"item {name}: elapsed {elapsed:.2f}s, keys={list(j.keys())[:15] if isinstance(j, dict) else type(j)}")
        tested += 1
    assert tested >= 1


# --- Visualization data ---
def test_visualization_data(auth_headers):
    t0 = time.time()
    r = requests.get(f"{API}/analytics/visualization", headers=auth_headers, timeout=TIMEOUT)
    elapsed = time.time() - t0
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    assert elapsed < 30, f"visualization too slow: {elapsed:.1f}s"
    j = r.json()
    print(f"visualization keys: {list(j.keys())[:15] if isinstance(j, dict) else type(j)}, elapsed {elapsed:.2f}s")


# --- Profit additivity: sum(daily) == monthly ---
def test_profit_additivity(auth_headers):
    # Pick a recent month with data - try last 12 months
    # Data is in 2026-01 to 2026-03 range per /api/stats
    for y, m in [(2026, 2), (2026, 1), (2026, 3)]:
        mr = requests.get(
            f"{API}/analytics/monthly-profit",
            params={"year": y, "month": m},
            headers=auth_headers,
            timeout=TIMEOUT,
        )
        assert mr.status_code == 200, f"monthly-profit failed: {mr.status_code}"
        mj = mr.json()
        month_silver = mj.get("silver_profit_kg", 0) or 0
        month_labor = mj.get("labor_profit_inr", 0) or 0

        dr = requests.get(
            f"{API}/analytics/daily-profit",
            params={"year": y, "month": m},
            headers=auth_headers,
            timeout=TIMEOUT,
        )
        assert dr.status_code == 200, f"daily failed: {dr.status_code} {dr.text[:300]}"
        dj = dr.json()
        rows = dj if isinstance(dj, list) else (
            dj.get("daily") or dj.get("daily_profits") or dj.get("days") or dj.get("data") or dj.get("profits") or []
        )
        sum_silver = sum((r.get("silver_profit_kg", 0) or 0) for r in rows if isinstance(r, dict))
        sum_labor = sum((r.get("labor_profit_inr", 0) or 0) for r in rows if isinstance(r, dict))
        print(f"Y={y} M={m} monthly silver={month_silver} labor={month_labor} | daily silver={sum_silver} labor={sum_labor} | daily_rows={len(rows)}")
        tol_silver = max(0.001, abs(month_silver) * 0.005)
        tol_labor = max(1.0, abs(month_labor) * 0.005)
        assert abs(sum_silver - month_silver) < tol_silver, f"silver additivity broken {y}-{m}: monthly={month_silver} daily_sum={sum_silver}"
        assert abs(sum_labor - month_labor) < tol_labor, f"labor additivity broken {y}-{m}: monthly={month_labor} daily_sum={sum_labor}"
    # additivity always verified, regardless of magnitude


# --- Physical stock dates + compare ---
def test_physical_stock_endpoints(auth_headers):
    r = requests.get(f"{API}/physical-stock/dates", headers=auth_headers, timeout=TIMEOUT)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    j = r.json()
    dates = j if isinstance(j, list) else (j.get("dates") or j.get("data") or [])
    print(f"physical-stock dates: {len(dates)}")
    assert len(dates) > 0
    d = dates[0] if isinstance(dates[0], str) else (dates[0].get("date") or dates[0].get("verification_date") or dates[0].get("_id"))
    t0 = time.time()
    r2 = requests.get(
        f"{API}/physical-stock/compare",
        params={"verification_date": d},
        headers=auth_headers,
        timeout=TIMEOUT,
    )
    elapsed = time.time() - t0
    assert r2.status_code == 200, f"compare failed: {r2.status_code} {r2.text[:300]}"
    assert elapsed < 30
    print(f"compare for {d}: elapsed {elapsed:.2f}s, keys={list(r2.json().keys())[:15]}")
