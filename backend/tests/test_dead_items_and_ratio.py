"""Tests for Stock:Sale ratio fix (baseline anchored) and Dead Items feature."""
import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": "admin", "password": "admin123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def sm_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": "TEST_SM", "password": "sm123"}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"TEST_SM login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


# ---------------- Backend ratio fix ----------------
class TestRatioFix:
    def test_sales_report_2025_bs053_anchor(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/analytics/sales-report",
                         params={"year": 2025, "month": 0},
                         headers=admin_headers, timeout=180)
        assert r.status_code == 200, r.text
        data = r.json()
        by_item = data.get("by_item") or data.get("items") or []
        assert by_item, "by_item empty"
        bs = next((x for x in by_item if (x.get("item_name") or x.get("stamp")) == "BS-053"), None)
        assert bs is not None, "BS-053 missing from by_item"
        # avg_stock_kg ≈ 313.567
        avg_stock = bs.get("avg_stock_kg")
        assert avg_stock is not None, f"avg_stock_kg missing: {bs}"
        assert 310 < avg_stock < 317, f"BS-053 avg_stock_kg out of range: {avg_stock}"
        ratio = bs.get("stock_sale_ratio")
        assert ratio is not None and 80 < ratio < 95, f"BS-053 ratio off: {ratio}"
        # Sanity: no absurd ratios
        ratios = [x.get("stock_sale_ratio") for x in by_item if x.get("stock_sale_ratio") is not None]
        extreme = [v for v in ratios if v > 2000]
        assert not extreme, f"Found absurd ratios >2000: {extreme[:5]}"

    def test_sales_report_2026(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/analytics/sales-report",
                         params={"year": 2026, "month": 0},
                         headers=admin_headers, timeout=180)
        assert r.status_code == 200
        by_item = r.json().get("by_item") or []
        non_null = [x for x in by_item if x.get("stock_sale_ratio") is not None]
        assert non_null, "2026 all months — no non-null ratios"

    def test_sales_report_before_baseline(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/analytics/sales-report",
                         params={"start_date": "2022-01-01", "end_date": "2022-06-30"},
                         headers=admin_headers, timeout=180)
        assert r.status_code == 200, r.text
        by_item = r.json().get("by_item") or []
        # Before baseline → ratios should be None/null
        for row in by_item:
            assert row.get("stock_sale_ratio") in (None, 0, 0.0) or row.get("stock_sale_ratio") is None, \
                f"Pre-baseline row has ratio: {row}"


# ---------------- Baseline seed ----------------
class TestBaselineSeed:
    def test_baseline_count_358(self, admin_headers):
        # Direct DB check via mongo
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        assert mongo_url and db_name
        client = MongoClient(mongo_url)
        count = client[db_name]["stock_sale_baseline"].count_documents({})
        assert count == 358, f"Expected 358 baseline docs, got {count}"


# ---------------- Dead Items ----------------
class TestDeadItems:
    def test_dead_items_admin(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/analytics/dead-items",
                         headers=admin_headers, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d, d
        items = d["items"]
        assert items, "dead-items empty"
        ms = d.get("months_span")
        assert ms and 44 < ms < 47, f"months_span off: {ms}"
        # No near-zero stock
        for it in items:
            assert it["stock_net_kg"] >= 0.05, f"low stock item slipped in: {it}"
            # required fields
            for k in ("item_name", "stamp", "merged_names", "sold_net_kg",
                      "avg_monthly_sale_kg", "stock_sale_ratio", "last_sale_date"):
                assert k in it, f"missing {k}: {it}"
        # Math check — allow rounding slop (avg is rounded to 3 decimals,
        # relative error only meaningful when avg > 0.05)
        for it in items:
            avg = it.get("avg_monthly_sale_kg")
            ratio = it.get("stock_sale_ratio")
            if avg and avg > 0.05 and ratio is not None:
                expected = it["stock_net_kg"] / avg
                assert abs(expected - ratio) / max(expected, 1e-6) < 0.05, \
                    f"ratio math wrong: {it}"

    def test_dead_items_forbidden_for_sm(self, sm_token):
        r = requests.get(f"{BASE_URL}/api/analytics/dead-items",
                         headers={"Authorization": f"Bearer {sm_token}"}, timeout=60)
        assert r.status_code == 403, r.status_code


# ---------------- Remove/Restore ----------------
class TestRemoveRestore:
    def test_remove_restore_flow(self, admin_headers):
        # Pick first item from current list
        r = requests.get(f"{BASE_URL}/api/analytics/dead-items",
                         headers=admin_headers, timeout=120)
        assert r.status_code == 200
        items = r.json()["items"]
        target = next((x["item_name"] for x in items if x["item_name"] == "SIKKI KADA 80"), None)
        if not target:
            target = items[0]["item_name"]

        # Remove
        rr = requests.post(f"{BASE_URL}/api/dead-items/remove",
                          json={"item_name": target},
                          headers=admin_headers, timeout=60)
        assert rr.status_code in (200, 201), rr.text

        # Verify
        r2 = requests.get(f"{BASE_URL}/api/analytics/dead-items",
                          headers=admin_headers, timeout=120)
        assert r2.status_code == 200
        d2 = r2.json()
        names = [x["item_name"] for x in d2["items"]]
        assert target not in names, f"{target} still in items after remove"
        removed = d2.get("removed") or []
        rec = next((x for x in removed if x["item_name"] == target), None)
        assert rec, f"{target} not in removed[]"
        assert rec.get("removed_by") == "admin", f"removed_by wrong: {rec}"

        # Restore
        rs = requests.post(f"{BASE_URL}/api/dead-items/restore",
                           json={"item_name": target},
                           headers=admin_headers, timeout=60)
        assert rs.status_code == 200, rs.text

        r3 = requests.get(f"{BASE_URL}/api/analytics/dead-items",
                          headers=admin_headers, timeout=120)
        names3 = [x["item_name"] for x in r3.json()["items"]]
        assert target in names3, f"{target} not restored"

    def test_restore_unknown_404(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/dead-items/restore",
                          json={"item_name": "ZZZ_NOT_A_REAL_ITEM_XYZ"},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 404, r.status_code

    def test_remove_empty_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/dead-items/remove",
                          json={"item_name": ""},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400, r.status_code

    def test_sm_forbidden_remove_restore(self, sm_token):
        h = {"Authorization": f"Bearer {sm_token}"}
        r1 = requests.post(f"{BASE_URL}/api/dead-items/remove",
                           json={"item_name": "X"}, headers=h, timeout=30)
        r2 = requests.post(f"{BASE_URL}/api/dead-items/restore",
                           json={"item_name": "X"}, headers=h, timeout=30)
        assert r1.status_code == 403
        assert r2.status_code == 403
