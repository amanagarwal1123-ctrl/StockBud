"""
Test: Physical Stock Baseline Feature
- When user approves physical stock values, they become inventory baselines
- Current Stock = baseline + post-baseline transactions (instead of opening stock)
- Reverse session removes baselines and Current Stock reverts to book values
- Rejected rows have final_gr_wt == old_gr_wt and gr_delta == 0
"""
import pytest
import httpx
import pymongo
import os
import io
import openpyxl
from datetime import datetime

BASE = "http://localhost:8001/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

client = pymongo.MongoClient(MONGO_URL)
db = client[DB_NAME]

# Use a far-future date for isolation
TEST_DATE = "2099-01-15"
TEST_ITEM_A = "TEST-BASELINE-ITEM-A"
TEST_ITEM_B = "TEST-BASELINE-ITEM-B"


def _make_excel(rows):
    """Create an in-memory Excel file with given rows [{item_name, gr_wt}]."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Item Name", "Gr.Wt."])
    for r in rows:
        ws.append([r["item_name"], r["gr_wt"]])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _login():
    resp = httpx.post(f"{BASE}/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up test data before and after each test."""
    # Cleanup before
    db.physical_stock.delete_many({"verification_date": TEST_DATE})
    db.physical_stock_update_sessions.delete_many({"verification_date": TEST_DATE})
    db.inventory_baselines.delete_many({"item_key": {"$in": [TEST_ITEM_A.lower(), TEST_ITEM_B.lower()]}})
    db.opening_stock.delete_many({"item_name": {"$in": [TEST_ITEM_A, TEST_ITEM_B]}})
    db.transactions.delete_many({"item_name": {"$in": [TEST_ITEM_A, TEST_ITEM_B]}})
    yield
    # Cleanup after
    db.physical_stock.delete_many({"verification_date": TEST_DATE})
    db.physical_stock_update_sessions.delete_many({"verification_date": TEST_DATE})
    db.inventory_baselines.delete_many({"item_key": {"$in": [TEST_ITEM_A.lower(), TEST_ITEM_B.lower()]}})
    db.opening_stock.delete_many({"item_name": {"$in": [TEST_ITEM_A, TEST_ITEM_B]}})
    db.transactions.delete_many({"item_name": {"$in": [TEST_ITEM_A, TEST_ITEM_B]}})


def _seed_physical_stock():
    """Seed two items in physical_stock for the test date."""
    db.physical_stock.insert_many([
        {"item_name": TEST_ITEM_A, "gr_wt": 5000, "net_wt": 4500, "verification_date": TEST_DATE, "stamp": "TEST-STAMP"},
        {"item_name": TEST_ITEM_B, "gr_wt": 3000, "net_wt": 2700, "verification_date": TEST_DATE, "stamp": "TEST-STAMP"},
    ])


def _seed_opening_stock():
    """Seed opening stock for test items."""
    db.opening_stock.insert_many([
        {"item_name": TEST_ITEM_A, "gr_wt": 10000, "net_wt": 9000, "stamp": "TEST-STAMP", "pc": 0, "fine": 0, "labor_wt": 0, "labor_rs": 0, "rate": 0, "total": 0},
        {"item_name": TEST_ITEM_B, "gr_wt": 8000, "net_wt": 7200, "stamp": "TEST-STAMP", "pc": 0, "fine": 0, "labor_wt": 0, "labor_rs": 0, "rate": 0, "total": 0},
    ])


def _seed_transactions(date):
    """Seed transactions for test items on a specific date."""
    db.transactions.insert_many([
        {"item_name": TEST_ITEM_A, "type": "purchase", "date": date, "gr_wt": 2000, "net_wt": 1800, "stamp": "TEST-STAMP", "refno": "T001"},
        {"item_name": TEST_ITEM_B, "type": "sale", "date": date, "gr_wt": 1000, "net_wt": 900, "stamp": "TEST-STAMP", "refno": "T002"},
    ])


class TestInventoryBaselineCreation:
    """Test that approving physical stock creates inventory baselines."""

    def test_baseline_created_on_approve(self):
        """
        When items are approved in physical stock, inventory_baselines should be created.
        """
        _seed_physical_stock()
        token = _login()
        headers = {"Authorization": f"Bearer {token}"}

        # Upload preview
        excel = _make_excel([
            {"item_name": TEST_ITEM_A, "gr_wt": 6.0},  # 6kg = 6000g
        ])
        resp = httpx.post(
            f"{BASE}/physical-stock/upload-preview?verification_date={TEST_DATE}",
            headers=headers,
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200, f"Preview failed: {resp.text}"
        data = resp.json()
        session_id = data["preview_session_id"]
        preview_rows = data["preview_rows"]

        # Approve the item
        item_row = preview_rows[0]
        resp = httpx.post(
            f"{BASE}/physical-stock/apply-updates",
            headers=headers,
            json={
                "verification_date": TEST_DATE,
                "preview_session_id": session_id,
                "items": [{"item_name": TEST_ITEM_A, "new_gr_wt": item_row["new_gr_wt"], "new_net_wt": item_row.get("new_net_wt", 0)}],
            },
        )
        assert resp.status_code == 200, f"Apply failed: {resp.text}"
        assert resp.json()["updated_count"] == 1

        # Verify baseline was created in inventory_baselines collection
        baseline = db.inventory_baselines.find_one({"item_key": TEST_ITEM_A.lower()}, {"_id": 0})
        assert baseline is not None, "Baseline should be created for approved item"
        assert baseline["item_name"] == TEST_ITEM_A
        assert baseline["baseline_date"] == TEST_DATE
        assert baseline["gr_wt"] == 6000.0
        assert baseline["session_id"] == session_id
        print(f"✓ Baseline created: {baseline}")

    def test_baseline_only_for_approved_items(self):
        """
        Only approved items should have baselines; rejected items should not.
        """
        _seed_physical_stock()
        token = _login()
        headers = {"Authorization": f"Bearer {token}"}

        excel = _make_excel([
            {"item_name": TEST_ITEM_A, "gr_wt": 6.0},
            {"item_name": TEST_ITEM_B, "gr_wt": 4.0},
        ])
        resp = httpx.post(
            f"{BASE}/physical-stock/upload-preview?verification_date={TEST_DATE}",
            headers=headers,
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        data = resp.json()
        session_id = data["preview_session_id"]
        preview_rows = data["preview_rows"]

        # Approve only ITEM_A
        item_a_row = next(r for r in preview_rows if r["item_name"] == TEST_ITEM_A)
        resp = httpx.post(
            f"{BASE}/physical-stock/apply-updates",
            headers=headers,
            json={
                "verification_date": TEST_DATE,
                "preview_session_id": session_id,
                "items": [{"item_name": TEST_ITEM_A, "new_gr_wt": item_a_row["new_gr_wt"], "new_net_wt": 0}],
            },
        )
        assert resp.status_code == 200

        # Finalize session (ITEM_B becomes rejected)
        resp = httpx.post(
            f"{BASE}/physical-stock/finalize-session",
            headers=headers,
            json={"session_id": session_id},
        )
        assert resp.status_code == 200

        # Verify baselines
        baseline_a = db.inventory_baselines.find_one({"item_key": TEST_ITEM_A.lower()})
        baseline_b = db.inventory_baselines.find_one({"item_key": TEST_ITEM_B.lower()})
        assert baseline_a is not None, "Baseline should exist for approved ITEM_A"
        assert baseline_b is None, "Baseline should NOT exist for rejected ITEM_B"
        print(f"✓ Baseline exists only for approved item A")


class TestCurrentStockCalculation:
    """Test that Current Stock uses baseline + post-baseline transactions."""

    def test_current_stock_uses_baseline(self):
        """
        Current Stock for baseline items = baseline value + transactions AFTER baseline_date.
        Non-baseline items retain normal book calculation (opening + all transactions).
        """
        _seed_opening_stock()
        _seed_physical_stock()
        token = _login()
        headers = {"Authorization": f"Bearer {token}"}

        # Add transactions BEFORE baseline date (2099-01-10)
        db.transactions.insert_one({
            "item_name": TEST_ITEM_A, "type": "purchase", "date": "2099-01-10",
            "gr_wt": 2000, "net_wt": 1800, "stamp": "TEST-STAMP", "refno": "PRE-1"
        })

        # Get current stock BEFORE approval - should be opening + transactions
        resp = httpx.get(f"{BASE}/inventory/current", headers=headers)
        assert resp.status_code == 200
        inventory = resp.json()["inventory"]
        item_a_before = next((i for i in inventory if i["item_name"] == TEST_ITEM_A), None)
        
        if item_a_before:
            # Before baseline: opening (10000) + purchase (2000) = 12000 gross
            expected_before = 10000 + 2000
            print(f"Before baseline - Item A gr_wt: {item_a_before['gr_wt']}, expected: {expected_before}")

        # Create baseline by approving physical stock
        excel = _make_excel([{"item_name": TEST_ITEM_A, "gr_wt": 6.0}])  # 6000g baseline
        resp = httpx.post(
            f"{BASE}/physical-stock/upload-preview?verification_date={TEST_DATE}",
            headers=headers,
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        session_id = resp.json()["preview_session_id"]
        preview_rows = resp.json()["preview_rows"]
        
        resp = httpx.post(
            f"{BASE}/physical-stock/apply-updates",
            headers=headers,
            json={
                "verification_date": TEST_DATE,
                "preview_session_id": session_id,
                "items": [{"item_name": TEST_ITEM_A, "new_gr_wt": preview_rows[0]["new_gr_wt"], "new_net_wt": 0}],
            },
        )
        assert resp.status_code == 200

        # Add transaction AFTER baseline date (2099-01-20)
        db.transactions.insert_one({
            "item_name": TEST_ITEM_A, "type": "purchase", "date": "2099-01-20",
            "gr_wt": 500, "net_wt": 450, "stamp": "TEST-STAMP", "refno": "POST-1"
        })

        # Get current stock AFTER approval - should be baseline + post-baseline transactions
        resp = httpx.get(f"{BASE}/inventory/current", headers=headers)
        assert resp.status_code == 200
        inventory = resp.json()["inventory"]
        item_a_after = next((i for i in inventory if i["item_name"] == TEST_ITEM_A), None)
        
        if item_a_after:
            # After baseline: baseline (6000) + post-baseline purchase (500) = 6500 gross
            # The pre-baseline transaction should NOT count
            expected_after = 6000 + 500
            print(f"After baseline - Item A gr_wt: {item_a_after['gr_wt']}, expected: {expected_after}")
            assert abs(item_a_after['gr_wt'] - expected_after) < 1, \
                f"Current stock should be baseline + post-baseline txns: got {item_a_after['gr_wt']}, expected {expected_after}"
            print(f"✓ Current stock correctly uses baseline: {item_a_after['gr_wt']}")

    def test_transactions_on_baseline_date_not_counted(self):
        """
        Transactions on or before baseline_date should not be counted for baseline items.
        """
        _seed_opening_stock()
        _seed_physical_stock()
        token = _login()
        headers = {"Authorization": f"Bearer {token}"}

        # Create baseline
        excel = _make_excel([{"item_name": TEST_ITEM_A, "gr_wt": 5.0}])
        resp = httpx.post(
            f"{BASE}/physical-stock/upload-preview?verification_date={TEST_DATE}",
            headers=headers,
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        session_id = resp.json()["preview_session_id"]
        preview_rows = resp.json()["preview_rows"]
        
        resp = httpx.post(
            f"{BASE}/physical-stock/apply-updates",
            headers=headers,
            json={
                "verification_date": TEST_DATE,
                "preview_session_id": session_id,
                "items": [{"item_name": TEST_ITEM_A, "new_gr_wt": preview_rows[0]["new_gr_wt"], "new_net_wt": 0}],
            },
        )
        assert resp.status_code == 200

        # Add transaction ON the baseline date (same day)
        db.transactions.insert_one({
            "item_name": TEST_ITEM_A, "type": "purchase", "date": TEST_DATE,
            "gr_wt": 1000, "net_wt": 900, "stamp": "TEST-STAMP", "refno": "SAME-DAY"
        })

        # Get current stock
        resp = httpx.get(f"{BASE}/inventory/current", headers=headers)
        inventory = resp.json()["inventory"]
        item_a = next((i for i in inventory if i["item_name"] == TEST_ITEM_A), None)
        
        if item_a:
            # Transaction on same day should NOT count
            expected = 5000  # baseline only
            print(f"Item A gr_wt: {item_a['gr_wt']}, expected: {expected}")
            assert abs(item_a['gr_wt'] - expected) < 1, \
                f"Same-day transaction should not count: got {item_a['gr_wt']}, expected {expected}"
            print(f"✓ Transactions on baseline_date correctly excluded")


class TestReverseSessionRemovesBaseline:
    """Test that reversing a session removes baselines and reverts Current Stock."""

    def test_reverse_removes_baseline(self):
        """
        Reversing a physical stock session should:
        1. Remove the inventory baseline for that item
        2. Cause Current Stock to revert to book calculation
        """
        _seed_opening_stock()
        _seed_physical_stock()
        token = _login()
        headers = {"Authorization": f"Bearer {token}"}

        # Create and approve baseline
        excel = _make_excel([{"item_name": TEST_ITEM_A, "gr_wt": 6.0}])
        resp = httpx.post(
            f"{BASE}/physical-stock/upload-preview?verification_date={TEST_DATE}",
            headers=headers,
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        session_id = resp.json()["preview_session_id"]
        preview_rows = resp.json()["preview_rows"]
        
        resp = httpx.post(
            f"{BASE}/physical-stock/apply-updates",
            headers=headers,
            json={
                "verification_date": TEST_DATE,
                "preview_session_id": session_id,
                "items": [{"item_name": TEST_ITEM_A, "new_gr_wt": preview_rows[0]["new_gr_wt"], "new_net_wt": 0}],
            },
        )
        assert resp.status_code == 200

        # Finalize session
        resp = httpx.post(
            f"{BASE}/physical-stock/finalize-session",
            headers=headers,
            json={"session_id": session_id},
        )
        assert resp.status_code == 200

        # Verify baseline exists
        baseline = db.inventory_baselines.find_one({"item_key": TEST_ITEM_A.lower()})
        assert baseline is not None, "Baseline should exist before reverse"

        # Reverse the session
        resp = httpx.post(
            f"{BASE}/physical-stock/update-history/{session_id}/reverse",
            headers=headers,
        )
        assert resp.status_code == 200, f"Reverse failed: {resp.text}"
        reverse_data = resp.json()
        print(f"Reverse response: {reverse_data}")

        # Verify baseline is removed
        baseline_after = db.inventory_baselines.find_one({"item_key": TEST_ITEM_A.lower()})
        assert baseline_after is None, "Baseline should be removed after reverse"
        print(f"✓ Baseline removed after reverse")

        # Verify current stock reverts to book calculation
        resp = httpx.get(f"{BASE}/inventory/current", headers=headers)
        inventory = resp.json()["inventory"]
        item_a = next((i for i in inventory if i["item_name"] == TEST_ITEM_A), None)
        
        if item_a:
            # After reverse: should be opening stock = 10000
            expected = 10000
            print(f"After reverse - Item A gr_wt: {item_a['gr_wt']}, expected: {expected}")
            assert abs(item_a['gr_wt'] - expected) < 1, \
                f"Current stock should revert to book value: got {item_a['gr_wt']}, expected {expected}"
            print(f"✓ Current stock reverted to book value")


class TestRejectedRowWeights:
    """Test that rejected rows have correct weight values."""

    def test_rejected_rows_have_old_weights(self):
        """
        Rejected rows in finalized sessions should have:
        - final_gr_wt == old_gr_wt
        - gr_delta == 0
        """
        _seed_physical_stock()
        token = _login()
        headers = {"Authorization": f"Bearer {token}"}

        # Upload preview for both items
        excel = _make_excel([
            {"item_name": TEST_ITEM_A, "gr_wt": 7.0},
            {"item_name": TEST_ITEM_B, "gr_wt": 4.0},
        ])
        resp = httpx.post(
            f"{BASE}/physical-stock/upload-preview?verification_date={TEST_DATE}",
            headers=headers,
            files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        data = resp.json()
        session_id = data["preview_session_id"]
        preview_rows = data["preview_rows"]

        # Approve only ITEM_A
        item_a_row = next(r for r in preview_rows if r["item_name"] == TEST_ITEM_A)
        resp = httpx.post(
            f"{BASE}/physical-stock/apply-updates",
            headers=headers,
            json={
                "verification_date": TEST_DATE,
                "preview_session_id": session_id,
                "items": [{"item_name": TEST_ITEM_A, "new_gr_wt": item_a_row["new_gr_wt"], "new_net_wt": 0}],
            },
        )
        assert resp.status_code == 200

        # Finalize session
        resp = httpx.post(
            f"{BASE}/physical-stock/finalize-session",
            headers=headers,
            json={"session_id": session_id},
        )
        assert resp.status_code == 200

        # Verify session in DB
        session = db.physical_stock_update_sessions.find_one({"session_id": session_id}, {"_id": 0})
        assert session["session_state"] == "finalized"

        for item in session["items"]:
            if item["item_name"] == TEST_ITEM_A:
                assert item["status"] == "applied"
                print(f"✓ ITEM_A applied: final_gr_wt={item['final_gr_wt']}, gr_delta={item['gr_delta']}")
            elif item["item_name"] == TEST_ITEM_B:
                assert item["status"] == "rejected", f"Expected rejected, got {item['status']}"
                assert item["final_gr_wt"] == item["old_gr_wt"], \
                    f"Rejected row final_gr_wt={item['final_gr_wt']} != old_gr_wt={item['old_gr_wt']}"
                assert item["gr_delta"] == 0, \
                    f"Rejected row gr_delta should be 0, got {item['gr_delta']}"
                print(f"✓ ITEM_B rejected: final_gr_wt={item['final_gr_wt']} == old_gr_wt={item['old_gr_wt']}, gr_delta={item['gr_delta']}")


class TestNonBaselineItemsNormalCalculation:
    """Test that non-baseline items retain normal book calculation."""

    def test_non_baseline_item_uses_opening_stock(self):
        """
        Items without baselines should use: opening stock + ALL transactions (normal book calculation).
        """
        _seed_opening_stock()
        token = _login()
        headers = {"Authorization": f"Bearer {token}"}

        # Add transactions for ITEM_B (no baseline will be created)
        db.transactions.insert_many([
            {"item_name": TEST_ITEM_B, "type": "purchase", "date": "2099-01-10", "gr_wt": 1000, "net_wt": 900, "stamp": "TEST-STAMP", "refno": "B-1"},
            {"item_name": TEST_ITEM_B, "type": "sale", "date": "2099-01-12", "gr_wt": 500, "net_wt": 450, "stamp": "TEST-STAMP", "refno": "B-2"},
        ])

        # Get current stock
        resp = httpx.get(f"{BASE}/inventory/current", headers=headers)
        inventory = resp.json()["inventory"]
        item_b = next((i for i in inventory if i["item_name"] == TEST_ITEM_B), None)
        
        if item_b:
            # Non-baseline: opening (8000) + purchase (1000) - sale (500) = 8500
            expected = 8000 + 1000 - 500
            print(f"Item B (non-baseline) gr_wt: {item_b['gr_wt']}, expected: {expected}")
            assert abs(item_b['gr_wt'] - expected) < 1, \
                f"Non-baseline item should use book calculation: got {item_b['gr_wt']}, expected {expected}"
            print(f"✓ Non-baseline item correctly uses book calculation")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
