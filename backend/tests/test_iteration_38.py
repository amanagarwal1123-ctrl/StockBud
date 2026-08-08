"""Tests for iteration 38: approvals cache dedup, party-monthly-profit, analytics regressions."""
import os
import time
import concurrent.futures
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://sales-manager-role.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# --- Approvals flow ---
def test_manager_all_entries(H):
    r = requests.get(f"{BASE}/api/manager/all-entries", headers=H, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, (list, dict))


def _get_a_pending_stamp(H):
    r = requests.get(f"{BASE}/api/manager/all-entries", headers=H, timeout=60)
    data = r.json()
    entries = data if isinstance(data, list) else data.get("entries") or data.get("data") or []
    for e in entries:
        if (e.get("status") or "").lower() in ("pending", "pending_approval", ""):
            s = e.get("stamp") or e.get("stamp_number") or e.get("id")
            if s:
                return s
    # fallback: return any stamp
    if entries:
        return entries[0].get("stamp") or entries[0].get("stamp_number") or entries[0].get("id")
    return None


def test_approval_details_cached(H):
    stamp = _get_a_pending_stamp(H)
    if not stamp:
        pytest.skip("No entries available")
    url = f"{BASE}/api/manager/approval-details/{stamp}"
    t1 = time.time()
    r1 = requests.get(url, headers=H, timeout=60)
    d1 = time.time() - t1
    assert r1.status_code == 200, r1.text
    t2 = time.time()
    r2 = requests.get(url, headers=H, timeout=60)
    d2 = time.time() - t2
    assert r2.status_code == 200
    print(f"approval-details first={d1:.2f}s second={d2:.2f}s")
    # second should be faster (cached). Allow generous margin.
    assert d2 < max(0.5, d1)  # cached call should be sub-500ms or faster than first


def test_approval_details_concurrent(H):
    stamp = _get_a_pending_stamp(H)
    if not stamp:
        pytest.skip("No entries available")
    url = f"{BASE}/api/manager/approval-details/{stamp}"

    def _hit():
        return requests.get(url, headers=H, timeout=90)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda _: _hit(), range(4)))
    for r in results:
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"
    # payloads should be identical
    payloads = [r.json() for r in results]
    for p in payloads[1:]:
        assert p == payloads[0]


# --- Inventory cache ---
def test_inventory_current_cached(H):
    url = f"{BASE}/api/inventory/current"
    t1 = time.time()
    r1 = requests.get(url, headers=H, timeout=60)
    d1 = time.time() - t1
    assert r1.status_code == 200, r1.text
    t2 = time.time()
    r2 = requests.get(url, headers=H, timeout=60)
    d2 = time.time() - t2
    assert r2.status_code == 200
    j1, j2 = r1.json(), r2.json()
    assert j1 == j2, "cached response differs"
    print(f"inventory first={d1:.2f}s second={d2:.2f}s")
    # sanity: values close to spec
    net = j1.get("total_net_wt") or j1.get("total_net_weight") or 0
    items = j1.get("total_items", 0)
    print(f"total_net_wt={net} total_items={items}")
    # spec: ~15163 g (or 15.163 kg)
    assert items == 105 or abs(items - 105) <= 5
    assert (14000 <= net <= 17000) or (14 <= net <= 17), f"net_wt out of range: {net}"


# --- New endpoint party-monthly-profit ---
def test_party_monthly_profit_customer(H):
    url = f"{BASE}/api/analytics/party-monthly-profit/PANNA LAL JEWELLERS MEERUT"
    r = requests.get(url, headers=H, params={"year": 2026, "party_type": "customer"}, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    months = data.get("months") or data.get("data") or data
    # months should be list of 12 or dict keyed by month
    if isinstance(months, dict):
        m7 = months.get("7") or months.get(7)
    else:
        m7 = next((m for m in months if (m.get("month") == 7 or m.get("month_num") == 7)), None)
    assert m7, f"month 7 missing in {data}"
    silver = m7.get("silver_profit_kg")
    labor = m7.get("labor_profit_inr")
    netwt = m7.get("net_wt_kg")
    print(f"customer month 7: silver={silver} labor={labor} netwt={netwt}")
    assert silver is not None
    assert abs(silver - 6.014) < 0.05, f"silver={silver}"
    assert abs(labor - 55988.44) < 5, f"labor={labor}"
    assert abs(netwt - 38.909) < 0.1, f"netwt={netwt}"


def test_party_monthly_profit_supplier(H):
    url = f"{BASE}/api/analytics/party-monthly-profit/NITESH AGRA"
    r = requests.get(url, headers=H, params={"year": 2026, "party_type": "supplier"}, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    months = data.get("months") or data.get("data") or data
    def get_month(m):
        if isinstance(months, dict):
            return months.get(str(m)) or months.get(m)
        return next((x for x in months if (x.get("month") == m or x.get("month_num") == m)), None)
    m6 = get_month(6)
    m2 = get_month(2)
    m7 = get_month(7)
    assert m6 and m2 and m7
    print(f"supplier months 2/6/7: {m2}, {m6}, {m7}")
    assert (m6.get("silver_profit_kg") or 0) > 0
    assert (m6.get("net_wt_kg") or m6.get("purchased_kg") or 0) > 0
    silver6 = m6.get("silver_profit_kg") or 0
    assert abs(silver6 - 4.904) < 0.1, f"m6 silver={silver6}"


def test_party_monthly_profit_invalid_party(H):
    url = f"{BASE}/api/analytics/party-monthly-profit/NONEXISTENT_TEST_PARTY_XYZ"
    r = requests.get(url, headers=H, params={"year": 2026, "party_type": "customer"}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    months = data.get("months") or data.get("data") or data
    if isinstance(months, dict):
        vals = months.values()
    else:
        vals = months
    totals = 0
    for m in vals:
        totals += abs(m.get("silver_profit_kg", 0) or 0) + abs(m.get("labor_profit_inr", 0) or 0)
    assert totals == 0, f"expected all zero, got totals={totals}"


def test_party_type_matters(H):
    url = f"{BASE}/api/analytics/party-monthly-profit/NITESH AGRA"
    rs = requests.get(url, headers=H, params={"year": 2026, "party_type": "supplier"}, timeout=120)
    rc = requests.get(url, headers=H, params={"year": 2026, "party_type": "customer"}, timeout=120)
    assert rs.status_code == 200 and rc.status_code == 200
    assert rs.json() != rc.json()


# --- Analytics regressions ---
PARAMS = {"start_date": "2026-06-01", "end_date": "2026-07-15"}

def test_customer_profit(H):
    r = requests.get(f"{BASE}/api/analytics/customer-profit", headers=H, params=PARAMS, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    lst = data if isinstance(data, list) else (data.get("customers") or data.get("data") or [])
    assert lst, "empty customer profit"
    top = lst[0]
    print(f"top customer: {top}")
    # top expected PANNA LAL JEWELLERS MEERUT
    name = top.get("customer_name") or top.get("party") or top.get("customer") or top.get("name") or ""
    assert "PANNA LAL" in name.upper()
    silver = top.get("silver_profit_kg") or 0
    assert abs(silver - 6.014) < 0.1


def test_supplier_profit(H):
    r = requests.get(f"{BASE}/api/analytics/supplier-profit", headers=H, params=PARAMS, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    lst = data if isinstance(data, list) else (data.get("suppliers") or data.get("data") or [])
    assert lst
    top = lst[0]
    name = top.get("supplier_name") or top.get("party") or top.get("supplier") or top.get("name") or ""
    print(f"top supplier: {top}")
    assert "NITESH" in name.upper()
    tp = top.get("total_purchased_kg") or top.get("purchased_kg") or 0
    assert abs(tp - 227.535) < 1
    sp = top.get("silver_profit_kg") or 0
    assert abs(sp - 9.313) < 0.2
    items = top.get("items_count") or top.get("item_count") or 0
    assert items == 2


@pytest.mark.parametrize("path", [
    "/api/analytics/sales-summary",
    "/api/analytics/profit",
    "/api/analytics/party-analysis",
    "/api/analytics/visualization",
    "/api/mappings/unmapped",
    "/api/analytics/sales-report",
])
def test_endpoints_ok(H, path):
    r = requests.get(f"{BASE}{path}", headers=H, params=PARAMS, timeout=120)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data is not None
