"""Iteration 46 – Seasonal enabled switch & seasonal-items list endpoint."""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"


def _login(u, p):
    r = requests.post(f"{API}/auth/login", json={"username": u, "password": p}, timeout=30)
    assert r.status_code == 200, r.text[:400]
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin', 'admin123')}"}


@pytest.fixture(scope="module")
def exec_headers():
    return {"Authorization": f"Bearer {_login('TEST_EXEC', 'exec123')}"}


# Non-admin forbidden
def test_seasonal_items_non_admin_forbidden(exec_headers):
    r = requests.get(f"{API}/purchase-list/seasonal-items", headers=exec_headers, timeout=30)
    assert r.status_code == 403


# GET seasonal-items returns legacy migrated item
def test_seasonal_items_contains_gobi_legacy(admin_headers):
    r = requests.get(f"{API}/purchase-list/seasonal-items", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text[:400]
    data = r.json()
    assert "items" in data, data
    names = {i["item_name"]: i for i in data["items"]}
    assert "GOBI PAYAL 60-122" in names, f"legacy GOBI PAYAL 60-122 not returned. Got: {list(names.keys())}"
    gobi = names["GOBI PAYAL 60-122"]
    assert sorted(gobi.get("season_months") or []) == [7, 8, 9]
    assert gobi.get("seasonal_enabled") is True
    assert gobi.get("purview") == "RAJESH"


# purchase-list rows carry seasonal_enabled
def test_purchase_list_rows_carry_seasonal_enabled(admin_headers):
    r = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60)
    assert r.status_code == 200
    d = r.json()
    # find gobi in rows (visible if current month in [7,8,9])
    gobi = next((row for row in d["rows"] if row["item_name"] == "GOBI PAYAL 60-122"), None)
    if gobi:
        assert gobi.get("seasonal_enabled") is True
        assert sorted(gobi.get("season_months") or []) == [7, 8, 9]
    # pick a non-seasonal item
    non_seas = next((row for row in d["rows"]
                     if row["item_name"] != "GOBI PAYAL 60-122"
                     and not row.get("season_months")), None)
    assert non_seas is not None
    assert non_seas.get("seasonal_enabled") is False


# item-state: seasonal_enabled flag lifecycle
def test_seasonal_enabled_state_lifecycle(admin_headers):
    # find a candidate non-seasonal item, avoid GOBI/NAJARIYA
    d = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60).json()
    forbidden = {"GOBI PAYAL 60-122", "NAJARIYA PLAIN 92.5"}
    candidate = next((r for r in d["rows"]
                      if r["item_name"] not in forbidden
                      and not r.get("season_months")
                      and r.get("seasonal_enabled") is False), None)
    assert candidate, "no candidate item found"
    item = candidate["item_name"]

    try:
        # Enable seasonal with null months (empty selection)
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "seasonal_enabled": True, "season_months": None},
                          timeout=30)
        assert r.status_code == 200, r.text[:400]
        d = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60).json()
        row = next((r for r in d["rows"] if r["item_name"] == item), None)
        assert row is not None, "item disappeared with seasonal_enabled=True but no months (should show all year)"
        assert row["seasonal_enabled"] is True
        assert row.get("season_months") in (None, [])

        # Now set months=[8]
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "season_months": [8]}, timeout=30)
        assert r.status_code == 200
        d = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60).json()
        row = next((r for r in d["rows"] if r["item_name"] == item), None)
        # Server month may or may not be 8; but seasonal_enabled must be true; season_months = [8]
        # If server month is not 8, item will not be visible in rows — fetch via seasonal-items instead
        sr = requests.get(f"{API}/purchase-list/seasonal-items", headers=admin_headers, timeout=30).json()
        sitem = next((s for s in sr["items"] if s["item_name"] == item), None)
        assert sitem is not None, "item not in seasonal-items after enabling"
        assert sitem["seasonal_enabled"] is True
        assert sitem["season_months"] == [8]

        # Disable seasonal → clears months too
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "seasonal_enabled": False}, timeout=30)
        assert r.status_code == 200
        d = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60).json()
        row = next((r for r in d["rows"] if r["item_name"] == item), None)
        assert row is not None, "item disappeared after seasonal disable"
        assert row["seasonal_enabled"] is False
        assert row.get("season_months") in (None, [])
        # Not in seasonal-items
        sr = requests.get(f"{API}/purchase-list/seasonal-items", headers=admin_headers, timeout=30).json()
        assert not any(s["item_name"] == item for s in sr["items"]), "item still in seasonal-items after disable"
    finally:
        # Always reset
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item, "seasonal_enabled": False}, timeout=30)
