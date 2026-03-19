"""Test: rejected rows in finalized sessions must retain old weights, not proposed."""
import pytest
import httpx
import pymongo
import os
import io
import openpyxl

BASE = "http://localhost:8001/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

client = pymongo.MongoClient(MONGO_URL)
db = client[DB_NAME]

TEST_DATE = "2099-12-31"


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
    return resp.json()["access_token"]


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up test data before and after each test."""
    db.physical_stock.delete_many({"verification_date": TEST_DATE})
    db.physical_stock_update_sessions.delete_many({"verification_date": TEST_DATE})
    yield
    db.physical_stock.delete_many({"verification_date": TEST_DATE})
    db.physical_stock_update_sessions.delete_many({"verification_date": TEST_DATE})


def _seed_physical_stock():
    """Seed two items in physical_stock for the test date."""
    db.physical_stock.insert_many([
        {"item_name": "ITEM-ALPHA", "gr_wt": 8888, "net_wt": 7777, "verification_date": TEST_DATE},
        {"item_name": "ITEM-BETA", "gr_wt": 5555, "net_wt": 4444, "verification_date": TEST_DATE},
    ])


def test_rejected_rows_have_old_weights_after_finalize():
    """
    Flow: upload preview for 2 items → approve only ITEM-ALPHA → finalize session
    Expected: ITEM-BETA (rejected) should have final_gr_wt == old_gr_wt == 5555, gr_delta == 0
    """
    _seed_physical_stock()
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload preview with new weights for both items
    excel = _make_excel([
        {"item_name": "ITEM-ALPHA", "gr_wt": 10.0},   # 10kg = 10000g
        {"item_name": "ITEM-BETA", "gr_wt": 3.0},      # 3kg = 3000g
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
    assert len(preview_rows) == 2

    # Verify draft session has correct initial values (final = old for pending)
    session = db.physical_stock_update_sessions.find_one({"session_id": session_id}, {"_id": 0})
    for item in session["items"]:
        assert item["status"] == "pending"
        assert item["final_gr_wt"] == item["old_gr_wt"], \
            f"Draft pending row {item['item_name']}: final_gr_wt={item['final_gr_wt']} should == old_gr_wt={item['old_gr_wt']}"
        assert item["gr_delta"] == 0, \
            f"Draft pending row {item['item_name']}: gr_delta should be 0, got {item['gr_delta']}"

    # 2. Approve ONLY ITEM-ALPHA
    alpha_row = next(r for r in preview_rows if r["item_name"] == "ITEM-ALPHA")
    resp = httpx.post(
        f"{BASE}/physical-stock/apply-updates",
        headers=headers,
        json={
            "verification_date": TEST_DATE,
            "preview_session_id": session_id,
            "items": [{"item_name": "ITEM-ALPHA", "new_gr_wt": alpha_row["new_gr_wt"], "new_net_wt": alpha_row.get("new_net_wt", 0)}],
            "update_mode": data.get("update_mode", "gross_only"),
        },
    )
    assert resp.status_code == 200, f"Apply failed: {resp.text}"
    apply_data = resp.json()
    assert apply_data["updated_count"] == 1

    # 3. Finalize the session (ITEM-BETA remains pending → should become rejected)
    resp = httpx.post(
        f"{BASE}/physical-stock/finalize-session",
        headers=headers,
        json={"session_id": session_id},
    )
    assert resp.status_code == 200, f"Finalize failed: {resp.text}"

    # 4. Verify the session in DB
    session = db.physical_stock_update_sessions.find_one({"session_id": session_id}, {"_id": 0})
    assert session["session_state"] == "finalized"

    for item in session["items"]:
        if item["item_name"] == "ITEM-ALPHA":
            assert item["status"] == "applied"
            assert item["final_gr_wt"] == 10000.0, f"Applied row final_gr_wt should be 10000, got {item['final_gr_wt']}"
            assert item["gr_delta"] != 0  # Should have a real delta
        elif item["item_name"] == "ITEM-BETA":
            assert item["status"] == "rejected", f"Expected rejected, got {item['status']}"
            assert item["final_gr_wt"] == item["old_gr_wt"], \
                f"REJECTED row ITEM-BETA: final_gr_wt={item['final_gr_wt']} MUST equal old_gr_wt={item['old_gr_wt']}"
            assert item["gr_delta"] == 0, \
                f"REJECTED row ITEM-BETA: gr_delta={item['gr_delta']} MUST be 0"
            assert item["final_net_wt"] == item["old_net_wt"], \
                f"REJECTED row ITEM-BETA: final_net_wt={item['final_net_wt']} MUST equal old_net_wt={item['old_net_wt']}"
            assert item["net_delta"] == 0, \
                f"REJECTED row ITEM-BETA: net_delta={item['net_delta']} MUST be 0"


def test_all_rejected_session_abandoned():
    """
    Flow: upload preview → finalize without approving anything → session should be abandoned
    """
    _seed_physical_stock()
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}

    excel = _make_excel([{"item_name": "ITEM-ALPHA", "gr_wt": 10.0}])
    resp = httpx.post(
        f"{BASE}/physical-stock/upload-preview?verification_date={TEST_DATE}",
        headers=headers,
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    session_id = resp.json()["preview_session_id"]

    resp = httpx.post(
        f"{BASE}/physical-stock/finalize-session",
        headers=headers,
        json={"session_id": session_id},
    )
    assert resp.status_code == 200
    session = db.physical_stock_update_sessions.find_one({"session_id": session_id}, {"_id": 0})
    assert session["session_state"] == "abandoned"


def test_draft_items_start_with_old_weights():
    """Verify that newly created draft items have final_* == old_* and delta == 0."""
    _seed_physical_stock()
    token = _login()
    headers = {"Authorization": f"Bearer {token}"}

    excel = _make_excel([
        {"item_name": "ITEM-ALPHA", "gr_wt": 99.0},
        {"item_name": "ITEM-BETA", "gr_wt": 88.0},
    ])
    resp = httpx.post(
        f"{BASE}/physical-stock/upload-preview?verification_date={TEST_DATE}",
        headers=headers,
        files={"file": ("test.xlsx", excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    session_id = resp.json()["preview_session_id"]

    session = db.physical_stock_update_sessions.find_one({"session_id": session_id}, {"_id": 0})
    for item in session["items"]:
        assert item["status"] == "pending"
        assert item["final_gr_wt"] == item["old_gr_wt"], \
            f"{item['item_name']}: draft final_gr_wt={item['final_gr_wt']} != old_gr_wt={item['old_gr_wt']}"
        assert item["final_net_wt"] == item["old_net_wt"], \
            f"{item['item_name']}: draft final_net_wt={item['final_net_wt']} != old_net_wt={item['old_net_wt']}"
        assert item["gr_delta"] == 0
        assert item["net_delta"] == 0
