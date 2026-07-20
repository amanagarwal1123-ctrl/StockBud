"""
Iteration 39: Year Comparison + Stock Query Pruning regression tests
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://alias-mapping-debug.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# --- Stock regression after query pruning ---
def test_current_stock_regression(h):
    r = requests.get(f"{BASE_URL}/api/inventory/current", headers=h, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    tnw = d.get("total_net_wt") or d.get("total_net_weight") or d.get("total_kg")
    ti = d.get("total_items")
    print("STOCK:", tnw, ti)
    # ground truth ~15163 g and 105 items
    assert ti == 105, f"expected total_items 105, got {ti}"
    # tnw may be in grams (~15163) or kg (~15.163)
    assert (abs(tnw - 15163) < 5) or (abs(tnw - 15.163) < 0.05), f"unexpected total_net_wt {tnw}"


# --- Year comparison overview ---
def test_year_comparison_overview(h):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/overview", headers=h, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert sorted(d["years"]) == [2024, 2025, 2026], d["years"]
    yt = d["yearly_totals"]
    # yearly_totals is a list of dicts with 'year'
    if isinstance(yt, list):
        by = {x["year"]: x for x in yt}
    else:
        by = {int(k): v for k, v in yt.items()}
    y24, y25, y26 = by.get(2024), by.get(2025), by.get(2026)
    assert y24 and y25 and y26
    assert abs(y24["sales_kg"] - 852.934) < 0.5, y24
    assert abs(y25["sales_kg"] - 1060.154) < 0.5, y25
    assert abs(y26["sales_kg"] - 3487.531) < 5, y26
    # growth
    g25 = y25.get("sales_growth_pct")
    g26 = y26.get("sales_growth_pct")
    assert g25 is not None and abs(g25 - 24.3) < 1.0, g25
    assert g26 is not None and abs(g26 - 229.0) < 3.0, g26
    # monthly
    monthly = d["monthly"]["sales_kg"]
    m25 = monthly.get("2025") or monthly.get(2025)
    assert isinstance(m25, list) and len(m25) == 12
    assert all(x > 0 for x in m25), m25


def test_year_comparison_top_items(h):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/top?entity=items&limit=8", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    items = d.get("top")
    assert items and len(items) == 8, f"got {len(items) if items else 0}"
    first = items[0]
    assert "name" in first and "total_kg" in first
    assert "yearly" in first and "monthly" in first
    # string year keys, 12-element arrays
    mo = first["monthly"]
    key = next(iter(mo.keys()))
    assert isinstance(key, str)
    assert len(mo[key]) == 12


def test_year_comparison_top_customers(h):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/top?entity=customers&limit=8", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    items = d.get("top")
    assert items and len(items) > 0


def test_year_comparison_top_suppliers(h):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/top?entity=suppliers&limit=8", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    items = d.get("top")
    assert items and len(items) > 0


def test_year_comparison_top_bogus(h):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/top?entity=bogus&limit=8", headers=h, timeout=30)
    assert r.status_code == 400, r.text


def test_year_comparison_parties_and_detail(h):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/parties?party_type=customer", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    parties = d.get("parties") or d.get("data") or d
    assert isinstance(parties, list) and len(parties) > 0
    name = parties[0] if isinstance(parties[0], str) else parties[0].get("name")
    assert name
    r2 = requests.get(f"{BASE_URL}/api/analytics/year-comparison/party-detail",
                      params={"party": name, "party_type": "customer"}, headers=h, timeout=60)
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    monthly = d2["monthly"]
    for k in ["kg", "value", "silver_profit_kg", "labor_profit_inr"]:
        assert k in monthly, f"missing {k}"
        yr_key = next(iter(monthly[k].keys()))
        assert isinstance(yr_key, str)
        assert len(monthly[k][yr_key]) == 12
    assert "yearly_kg" in d2


def test_year_comparison_party_detail_unknown(h):
    r = requests.get(f"{BASE_URL}/api/analytics/year-comparison/party-detail",
                     params={"party": "___NOSUCH_PARTY_ZZZ___", "party_type": "customer"}, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    # Should be zeros, not 500
    assert "monthly" in d


# --- Analytics regressions ---
def test_customer_profit_regression(h):
    r = requests.get(f"{BASE_URL}/api/analytics/customer-profit",
                     params={"start_date": "2026-06-01", "end_date": "2026-07-15"}, headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    arr = d if isinstance(d, list) else (d.get("customers") or d.get("data") or d.get("results"))
    assert arr and len(arr) > 0
    top = arr[0]
    assert "PANNA LAL JEWELLERS MEERUT" == (top.get("customer_name") or top.get("name"))
    sp = top.get("silver_profit_kg") or top.get("silver_profit")
    assert abs(sp - 6.014) < 0.05, sp


def test_supplier_profit_regression(h):
    r = requests.get(f"{BASE_URL}/api/analytics/supplier-profit",
                     params={"start_date": "2026-06-01", "end_date": "2026-07-15"}, headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    arr = d if isinstance(d, list) else (d.get("suppliers") or d.get("data") or d.get("results"))
    assert arr and len(arr) > 0
    top = arr[0]
    assert "NITESH AGRA" == (top.get("supplier_name") or top.get("name"))
    tp = top.get("total_purchased_kg") or top.get("purchased_kg") or top.get("total_kg")
    assert abs(tp - 227.535) < 0.5, tp


def test_party_monthly_profit_regression(h):
    r = requests.get(f"{BASE_URL}/api/analytics/party-monthly-profit/PANNA%20LAL%20JEWELLERS%20MEERUT",
                     params={"year": 2026, "party_type": "customer"}, headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    months = d.get("months") or d.get("monthly") or d
    # Find month 7
    m7 = None
    if isinstance(months, list):
        for x in months:
            if x.get("month") == 7:
                m7 = x
                break
    elif isinstance(months, dict):
        m7 = months.get("7") or months.get(7)
    assert m7, f"no month 7: {d}"
    sp = m7.get("silver_profit_kg") or m7.get("silver_profit") or m7.get("silver")
    assert abs(sp - 6.014) < 0.05, sp


def test_stock_audit_uploads(h):
    r = requests.get(f"{BASE_URL}/api/stock-audit/uploads", headers=h, timeout=30)
    assert r.status_code == 200, r.text
