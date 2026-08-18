"""Backend tests for Purchase List & Goods to Arrive feature."""
import os
import time
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"


def _login(username, password):
    r = requests.post(f"{API}/auth/login", json={"username": username, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text[:300]}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin', 'admin123')}"}


@pytest.fixture(scope="module")
def exec_headers():
    return {"Authorization": f"Bearer {_login('TEST_EXEC', 'exec123')}"}


@pytest.fixture(scope="module")
def sm_headers():
    return {"Authorization": f"Bearer {_login('TEST_SM', 'sm123')}"}


# =============== GET /purchase-list ===============

class TestPurchaseListBasic:
    def test_admin_get_purchase_list(self, admin_headers):
        r = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert "date" in data and "baseline_start" in data and "orderers" in data and "rows" in data
        assert "Admin" in data["orderers"]
        # all rows: order_qty_kg > 0 and approx baseline - current stock
        for row in data["rows"]:
            assert row["order_qty_kg"] > 0, f"non-positive qty for {row['item_name']}"
            diff = abs(row["order_qty_kg"] - (row["baseline_kg"] - row["current_stock_kg"]))
            assert diff < 0.005, f"{row['item_name']}: {row['order_qty_kg']} vs {row['baseline_kg']}-{row['current_stock_kg']}"
        # default sort: profit_silver desc, nulls last
        vis = [r for r in data["rows"] if not r.get("temp_removed")]
        prev = None
        seen_null = False
        for row in vis:
            p = row.get("profit_silver_per_kg")
            if p is None:
                seen_null = True
            else:
                assert not seen_null, "non-null profit after a null one (nulls should be last)"
                if prev is not None:
                    assert p <= prev + 1e-6, f"not sorted desc: {prev} -> {p}"
                prev = p

    def test_non_admin_forbidden(self, exec_headers, sm_headers):
        endpoints = [
            ("GET", "/purchase-list"),
            ("POST", "/purchase-list/item-state"),
            ("POST", "/purchase-list/refresh"),
            ("POST", "/purchase-list/orderers"),
            ("PUT", "/purchase-list/config"),
            ("GET", "/goods-to-arrive"),
            ("PUT", "/goods-to-arrive/fake-id"),
        ]
        for method, path in endpoints:
            for hdrs, who in [(exec_headers, "exec"), (sm_headers, "sm")]:
                r = requests.request(method, f"{API}{path}", headers=hdrs, json={}, timeout=30)
                assert r.status_code == 403, f"{who} {method} {path} -> {r.status_code}"

    def test_past_date(self, admin_headers):
        from datetime import datetime, timezone, timedelta
        d = ((datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)) - timedelta(days=30)).strftime('%Y-%m-%d')
        r = requests.get(f"{API}/purchase-list", headers=admin_headers, params={"date": d}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        assert data["date"] == d
        assert isinstance(data["rows"], list)

    def test_invalid_date(self, admin_headers):
        r = requests.get(f"{API}/purchase-list", headers=admin_headers, params={"date": "not-a-date"}, timeout=30)
        assert r.status_code == 400


# =============== item-state mutations ===============

def _get_list(admin_headers):
    r = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60)
    r.raise_for_status()
    return r.json()


class TestItemStateAndGoods:
    @pytest.fixture(scope="class")
    def picked(self, admin_headers):
        d = _get_list(admin_headers)
        # Pick two distinct items to isolate state changes
        assert len(d["rows"]) >= 2, "Not enough rows for testing"
        return {"date": d["date"], "row_a": d["rows"][0], "row_b": d["rows"][1]}

    def test_green_creates_goods_order(self, admin_headers, picked):
        row = picked["row_a"]
        item = row["item_name"]
        # ensure clean
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item, "green": False}, timeout=30)
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "green": True, "date": picked["date"]}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        g = requests.get(f"{API}/goods-to-arrive", headers=admin_headers, timeout=30).json()
        matching = [o for o in g["to_arrive"] if o["item_name"] == item]
        assert matching, "green did not create goods order"
        o = matching[0]
        assert abs(o["order_qty_kg"] - row["order_qty_kg"]) < 0.01
        assert abs(o["fine_kg"] - row["fine_kg"]) < 0.01
        assert abs(o["labour_inr"] - row["labour_inr"]) < 1.0
        assert o["order_qty_kg"] > 0

    def test_green_false_removes(self, admin_headers, picked):
        item = picked["row_a"]["item_name"]
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "green": False}, timeout=30)
        assert r.status_code == 200
        g = requests.get(f"{API}/goods-to-arrive", headers=admin_headers, timeout=30).json()
        assert not [o for o in g["to_arrive"] if o["item_name"] == item]

    def test_temp_remove_and_refresh_preserves_green(self, admin_headers, picked):
        item_a = picked["row_a"]["item_name"]
        item_b = picked["row_b"]["item_name"]
        # Mark A green, temp-remove B
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item_a, "green": True, "date": picked["date"]}, timeout=30)
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item_b, "temp_removed": True}, timeout=30)
        d = _get_list(admin_headers)
        b_row = next(r for r in d["rows"] if r["item_name"] == item_b)
        assert b_row["temp_removed"] is True
        # refresh
        r = requests.post(f"{API}/purchase-list/refresh", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json().get("restored", 0) >= 1
        d = _get_list(admin_headers)
        b_row = next(r for r in d["rows"] if r["item_name"] == item_b)
        a_row = next(r for r in d["rows"] if r["item_name"] == item_a)
        assert b_row["temp_removed"] is False
        assert a_row["green"] is True, "green mark cleared by refresh"
        # cleanup
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item_a, "green": False}, timeout=30)

    def test_season_months_persist(self, admin_headers, picked):
        item = picked["row_a"]["item_name"]
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "season_months": [1, 2]}, timeout=30)
        assert r.status_code == 200
        d = _get_list(admin_headers)
        row = next(r for r in d["rows"] if r["item_name"] == item)
        assert row["season_months"] == [1, 2]
        # clear
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item, "season_months": []}, timeout=30)
        d = _get_list(admin_headers)
        row = next(r for r in d["rows"] if r["item_name"] == item)
        assert row["season_months"] is None

    def test_add_orderer_and_purview(self, admin_headers, picked):
        name = "TEST_ORDR_QA"
        r = requests.post(f"{API}/purchase-list/orderers", headers=admin_headers,
                          json={"name": name}, timeout=30)
        assert r.status_code == 200
        d = _get_list(admin_headers)
        assert name in d["orderers"]
        item = picked["row_a"]["item_name"]
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "purview": name}, timeout=30)
        assert r.status_code == 200
        d = _get_list(admin_headers)
        row = next(r for r in d["rows"] if r["item_name"] == item)
        assert row["purview"] == name
        # restore
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item, "purview": "Admin"}, timeout=30)

    def test_baseline_fixed_and_back(self, admin_headers, picked):
        item = picked["row_a"]["item_name"]
        fixed_val = 7.5
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "baseline_mode": "fixed", "fixed_baseline_kg": fixed_val},
                          timeout=30)
        assert r.status_code == 200
        d = _get_list(admin_headers)
        row = next((r for r in d["rows"] if r["item_name"] == item), None)
        # Might drop out if current_stock >= fixed_val
        if row:
            assert row["baseline_mode"] == "fixed"
            assert abs(row["baseline_kg"] - fixed_val) < 0.01
            assert abs(row["order_qty_kg"] - (fixed_val - row["current_stock_kg"])) < 0.01
        # revert
        r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": item, "baseline_mode": "variable"}, timeout=30)
        assert r.status_code == 200
        d = _get_list(admin_headers)
        row = next(r for r in d["rows"] if r["item_name"] == item)
        assert row["baseline_mode"] == "variable"


# =============== config ===============

class TestConfig:
    def test_baseline_start_change(self, admin_headers):
        r = requests.put(f"{API}/purchase-list/config", headers=admin_headers,
                         json={"baseline_start": "2026-03-01"}, timeout=30)
        assert r.status_code == 200
        d = _get_list(admin_headers)
        assert d["baseline_start"] == "2026-03-01"
        # restore
        r = requests.put(f"{API}/purchase-list/config", headers=admin_headers,
                         json={"baseline_start": "2026-01-01"}, timeout=30)
        assert r.status_code == 200
        d = _get_list(admin_headers)
        assert d["baseline_start"] == "2026-01-01"

    def test_invalid_baseline(self, admin_headers):
        r = requests.put(f"{API}/purchase-list/config", headers=admin_headers,
                         json={"baseline_start": "not-a-date"}, timeout=30)
        assert r.status_code == 400


# =============== goods lifecycle ===============

class TestGoodsLifecycle:
    def test_lifecycle(self, admin_headers):
        # create via green mark
        d = _get_list(admin_headers)
        item_row = d["rows"][0]
        item = item_row["item_name"]
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item, "green": True, "date": d["date"]}, timeout=30)
        g = requests.get(f"{API}/goods-to-arrive", headers=admin_headers, timeout=30).json()
        order = next(o for o in g["to_arrive"] if o["item_name"] == item)
        oid = order["id"]
        tunch = order["purchase_tunch"] or 0
        labour_per_kg = order["labour_per_kg"] or 0

        # edit qty
        r = requests.put(f"{API}/goods-to-arrive/{oid}", headers=admin_headers,
                         json={"order_qty_kg": 2.5}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        body = r.json()
        assert abs(body["order_qty_kg"] - 2.5) < 0.001
        assert abs(body["fine_kg"] - 2.5 * tunch / 100.0) < 0.01
        assert abs(body["labour_inr"] - round(2.5 * labour_per_kg)) < 1.0

        # arrive
        r = requests.put(f"{API}/goods-to-arrive/{oid}", headers=admin_headers,
                         json={"action": "arrive"}, timeout=30)
        assert r.status_code == 200
        g = requests.get(f"{API}/goods-to-arrive", headers=admin_headers, timeout=30).json()
        assert any(o["id"] == oid and o.get("arrived_at") for o in g["arrived"])
        assert not any(o["id"] == oid for o in g["to_arrive"])

        # undo
        r = requests.put(f"{API}/goods-to-arrive/{oid}", headers=admin_headers,
                         json={"action": "undo"}, timeout=30)
        assert r.status_code == 200
        g = requests.get(f"{API}/goods-to-arrive", headers=admin_headers, timeout=30).json()
        undone = next(o for o in g["to_arrive"] if o["id"] == oid)
        assert undone["arrived_at"] is None

        # cleanup: uncheck green removes it
        requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                      json={"item_name": item, "green": False}, timeout=30)
        g = requests.get(f"{API}/goods-to-arrive", headers=admin_headers, timeout=30).json()
        assert not any(o["item_name"] == item and o["status"] == "to_arrive" for o in g["to_arrive"])

    def test_unknown_id(self, admin_headers):
        r = requests.put(f"{API}/goods-to-arrive/nonexistent-id-xyz", headers=admin_headers,
                         json={"action": "arrive"}, timeout=30)
        assert r.status_code == 404
