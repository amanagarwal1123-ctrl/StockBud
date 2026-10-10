"""
Regression tests for chunked aggregation rewrite (iteration_58).
Verifies dead-items and sales-report endpoints return identical results after chunking.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stock-vs-sales.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- dead-items ---
def test_dead_items_shape_and_spot_check(headers):
    r = requests.get(f"{BASE_URL}/api/analytics/dead-items", headers=headers, timeout=120)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    items = data.get("items", [])
    assert len(items) == 85, f"expected 85 items, got {len(items)}"
    assert abs(data.get("months_span", 0) - 45.6) < 0.1, f"months_span={data.get('months_span')}"

    # 6 items with null stock_sale_ratio (Never sold)
    null_ratio = [i for i in items if i.get("stock_sale_ratio") is None]
    assert len(null_ratio) == 6, f"expected 6 null-ratio items, got {len(null_ratio)}"

    # No item with stock_net_kg < 0.05
    tiny = [i for i in items if (i.get("stock_net_kg") or 0) < 0.05]
    assert not tiny, f"found items with stock_net_kg<0.05: {tiny}"

    # Spot check SIKKI KADA 80
    sikki = next((i for i in items if i.get("item_name") == "SIKKI KADA 80"), None)
    assert sikki is not None, "SIKKI KADA 80 missing"
    assert abs(sikki["stock_sale_ratio"] - 562.32) < 1.0, f"SIKKI KADA 80 ratio={sikki['stock_sale_ratio']}"
    assert abs(sikki["stock_net_kg"] - 2.058) < 0.01, f"SIKKI KADA 80 stock={sikki['stock_net_kg']}"


# --- sales-report year=2025 month=0 baseline anchor ---
def test_sales_report_2025_baseline(headers):
    r = requests.get(f"{BASE_URL}/api/analytics/sales-report", params={"year": 2025, "month": 0}, headers=headers, timeout=120)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    by_item = data.get("by_item", [])
    bs053 = next((i for i in by_item if i.get("item_name") == "BS-053"), None)
    assert bs053 is not None, "BS-053 missing"
    assert abs(bs053["avg_stock_kg"] - 313.567) < 0.5, f"BS-053 avg_stock_kg={bs053['avg_stock_kg']}"
    assert abs(bs053["stock_sale_ratio"] - 86.01) < 0.5, f"BS-053 ratio={bs053['stock_sale_ratio']}"


# --- sales-report year=2026 month=0 ---
def test_sales_report_2026(headers):
    r = requests.get(f"{BASE_URL}/api/analytics/sales-report", params={"year": 2026, "month": 0}, headers=headers, timeout=120)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    data = r.json()
    by_item = data.get("by_item", [])
    sikki = next((i for i in by_item if i.get("item_name") == "SIKKI KADA 80"), None)
    assert sikki is not None, "SIKKI KADA 80 missing in 2026 report"
    assert sikki.get("stock_sale_ratio") is not None, f"SIKKI KADA 80 ratio null: {sikki}"


# --- Remove/restore ---
def test_remove_restore_kanha_set(headers):
    # Remove
    r = requests.post(f"{BASE_URL}/api/dead-items/remove", json={"item_name": "KANHA SET"}, headers=headers, timeout=30)
    assert r.status_code == 200, f"remove failed: {r.status_code} {r.text}"

    # Verify in removed[], not items[]
    r = requests.get(f"{BASE_URL}/api/analytics/dead-items", headers=headers, timeout=120)
    assert r.status_code == 200
    data = r.json()
    items_names = [i["item_name"] for i in data.get("items", [])]
    removed_names = [i["item_name"] for i in data.get("removed", [])]
    assert "KANHA SET" in removed_names, f"KANHA SET not in removed: {removed_names}"
    assert "KANHA SET" not in items_names, "KANHA SET still in items"

    # Restore
    r = requests.post(f"{BASE_URL}/api/dead-items/restore", json={"item_name": "KANHA SET"}, headers=headers, timeout=30)
    assert r.status_code == 200, f"restore failed: {r.status_code} {r.text}"

    # Verify removed is empty
    r = requests.get(f"{BASE_URL}/api/analytics/dead-items", headers=headers, timeout=120)
    assert r.status_code == 200
    data = r.json()
    removed_names_after = [i["item_name"] for i in data.get("removed", [])]
    assert "KANHA SET" not in removed_names_after, f"KANHA SET still in removed: {removed_names_after}"
