"""Iteration 40 tests: overview new metrics, zero-ledger skip, visualization,
seasonal DB cache, regression checks."""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://alias-mapping-debug.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


# ============ (1) Overview new metrics ============
def test_overview_new_metric_keys(hdr):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/overview", headers=hdr, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "monthly" in data and "yearly_totals" in data
    expected_keys = {"sales_kg", "sales_fine_kg", "sales_value",
                     "purchases_kg", "purchases_fine_kg",
                     "silver_profit_kg", "labor_profit_inr", "transactions"}
    assert set(data["monthly"].keys()) == expected_keys, f"got {set(data['monthly'].keys())}"

    # ground truth
    yt = {row["year"]: row for row in data["yearly_totals"]}
    assert round(yt[2024]["sales_kg"], 3) == 852.934
    assert round(yt[2024]["sales_fine_kg"], 3) == 743.863
    assert round(yt[2025]["sales_kg"], 3) == 1060.154
    assert round(yt[2025]["sales_fine_kg"], 3) == 923.503
    assert round(yt[2026]["sales_kg"], 3) == 3487.531
    assert round(yt[2026]["sales_fine_kg"], 3) == 2222.666

    # silver_profit_kg/labor_profit_inr should be 0 (only 1 stamped item)
    for y in (2024, 2025, 2026):
        assert yt[y]["silver_profit_kg"] == 0.0, f"expected 0 for {y}"
        assert yt[y]["labor_profit_inr"] == 0.0, f"expected 0 for {y}"


# ============ (2) Zero-ledger skip ============
def test_customer_profit_zero_ledger_skip(hdr):
    r = requests.get(f"{BASE_URL}/api/analytics/customer-profit",
                     params={"start_date": "2026-06-01", "end_date": "2026-07-15"},
                     headers=hdr, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    customers = data.get("customers", data if isinstance(data, list) else [])
    # top silver profit
    if customers:
        top = sorted(customers, key=lambda c: c.get("silver_profit_kg", 0), reverse=True)[0]
        print(f"TOP customer: {top.get('customer_name')} silver_profit_kg={top.get('silver_profit_kg')}")
    # verify code path present in server.py
    with open("/app/backend/server.py") as f:
        content = f.read()
    assert "if ledger_item is None" in content, "ledger skip code missing"


# ============ (3) Visualization single-pass ============
def test_visualization_multi_year_monthly(hdr):
    r = requests.get(f"{BASE_URL}/api/analytics/visualization",
                     params={"start_date": "2024-01-01", "end_date": "2026-12-31"},
                     headers=hdr, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("sales_by_item", "sales_by_party", "purchases_by_supplier",
              "sales_trend", "tier_distribution", "stock_health"):
        assert k in d, f"missing {k}"
    assert len(d["sales_by_item"]) <= 30
    assert d.get("trend_granularity") == "monthly", d.get("trend_granularity")


def test_visualization_short_range_daily(hdr):
    r = requests.get(f"{BASE_URL}/api/analytics/visualization",
                     params={"start_date": "2026-05-01", "end_date": "2026-06-15"},
                     headers=hdr, timeout=60)
    assert r.status_code == 200
    assert r.json().get("trend_granularity") == "daily"


# ============ (4) Seasonal compute + cache ============
def test_seasonal_compute_and_cache(hdr):
    r = requests.post(f"{BASE_URL}/api/seasonal/compute",
                      params={"force": "true"}, headers=hdr, timeout=180)
    assert r.status_code == 200, r.text
    body = r.json()
    print(f"compute body: {body}")
    # Poll status
    for _ in range(30):
        s = requests.get(f"{BASE_URL}/api/seasonal/status", headers=hdr, timeout=30)
        assert s.status_code == 200
        sj = s.json()
        if sj.get("status") in ("ready", "cached") or sj.get("cached"):
            print(f"status: {sj}")
            break
        time.sleep(2)
    else:
        pytest.fail(f"seasonal not ready: {sj}")

    pf = requests.get(f"{BASE_URL}/api/seasonal/pms-final", headers=hdr, timeout=60)
    assert pf.status_code == 200
    body = pf.json()
    # accept list or {items: []}
    items = body if isinstance(body, list) else body.get("items", body.get("data", []))
    assert isinstance(items, list)
    print(f"pms-final items: {len(items)}")


def test_seasonal_db_cache_doc():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = MongoClient(mongo_url)
    db = client[db_name]
    doc = db.app_cache.find_one({"_id": "seasonal_results"}) or \
          db.app_cache.find_one({"key": "seasonal_results"})
    assert doc is not None, "seasonal_results not persisted to db.app_cache"
    print(f"cache doc keys: {list(doc.keys())}")


# ============ (5) Regression ============
def test_regression_inventory_current(hdr):
    r = requests.get(f"{BASE_URL}/api/inventory/current", headers=hdr, timeout=60)
    assert r.status_code == 200
    d = r.json()
    net = d.get("total_net_wt") or d.get("summary", {}).get("total_net_wt")
    items = d.get("total_items") or d.get("summary", {}).get("total_items")
    assert net and abs(net - 15163) < 5, f"net={net}"
    assert items == 105, f"items={items}"


@pytest.mark.parametrize("lim", [10, 20, 30, 40, 50])
def test_top_items_limits(hdr, lim):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/top",
                     params={"entity": "items", "limit": lim}, headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    top = r.json().get("top", [])
    assert len(top) <= lim
    print(f"limit={lim} got={len(top)}")


def test_party_monthly_profit(hdr):
    r = requests.get(f"{BASE_URL}/api/analytics/party-monthly-profit/PANNA%20LAL%20JEWELLERS%20MEERUT",
                     params={"year": 2026}, headers=hdr, timeout=60)
    assert r.status_code == 200, r.text


def test_stock_audit_uploads(hdr):
    r = requests.get(f"{BASE_URL}/api/stock-audit/uploads", headers=hdr, timeout=30)
    assert r.status_code == 200
