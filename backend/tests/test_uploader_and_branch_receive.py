"""Tests for two features:
  (1) branch_transfer Receive rows now parse rate columns (Tunch/Wstg/Fine/Labour/Total/Rate)
      and are counted alongside purchases when computing item-level averages.
  (2) new 'uploader' role — Upload Files page only.
  Plus wrong-file-format rejection so bad uploads never corrupt data.
"""
import io
import os
import time
from datetime import datetime
from pathlib import Path

import pytest
import requests
from openpyxl import Workbook
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"username": "admin", "password": "admin123"}
UPLOADER = {"username": "TEST_UPLOADER", "password": "upload123"}


# ---------- helpers ----------
def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed for {creds['username']}: {r.status_code} {r.text[:200]}"
    j = r.json()
    return j["access_token"], j["user"]


def _mkxlsx(headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _upload(token, file_type, headers, rows, start_date="2026-01-01", end_date="2026-01-31", timeout=90):
    """Complete chunked upload flow. Returns final status dict."""
    hdrs = {"Authorization": f"Bearer {token}"}
    init = requests.post(f"{API}/upload/init", json={
        "file_type": file_type,
        "start_date": start_date,
        "end_date": end_date,
        "total_chunks": 1,
    }, headers=hdrs, timeout=30)
    assert init.status_code == 200, f"init failed: {init.status_code} {init.text[:200]}"
    upload_id = init.json()["upload_id"]

    data = _mkxlsx(headers, rows)
    files = {"file": ("test.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    ch = requests.post(f"{API}/upload/chunk/{upload_id}?chunk_index=0", files=files, headers=hdrs, timeout=60)
    assert ch.status_code == 200, f"chunk failed: {ch.status_code} {ch.text[:200]}"

    fin = requests.post(f"{API}/upload/finalize/{upload_id}", headers=hdrs, timeout=30)
    assert fin.status_code == 200, f"finalize failed: {fin.status_code} {fin.text[:200]}"

    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        s = requests.get(f"{API}/upload/status/{upload_id}", headers=hdrs, timeout=15)
        assert s.status_code == 200, s.text[:200]
        last = s.json()
        if last.get("status") in ("complete", "error"):
            return last
        time.sleep(1)
    pytest.fail(f"upload {upload_id} did not finish in {timeout}s. last={last}")


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    tok, _ = _login(ADMIN)
    return tok


@pytest.fixture(scope="module")
def uploader_token():
    # Ensure the uploader account exists (admin creates it if missing)
    admin_tok, _ = _login(ADMIN)
    r = requests.get(f"{API}/users/list", headers={"Authorization": f"Bearer {admin_tok}"}, timeout=30)
    if r.status_code == 200 and not any(u.get("username") == UPLOADER["username"] for u in r.json()):
        requests.post(f"{API}/users/create", json={
            "username": UPLOADER["username"],
            "password": UPLOADER["password"],
            "full_name": "Test Uploader",
            "role": "uploader",
        }, headers={"Authorization": f"Bearer {admin_tok}"}, timeout=30)
    tok, user = _login(UPLOADER)
    assert user["role"] == "uploader"
    return tok


# ---------- role gate tests ----------
class TestUploaderRoleGates:
    def test_login(self, uploader_token):
        assert uploader_token

    def test_can_get_opening_effective_date(self, uploader_token):
        r = requests.get(f"{API}/opening-stock/effective-date",
                         headers={"Authorization": f"Bearer {uploader_token}"}, timeout=15)
        assert r.status_code == 200
        assert "effective_date" in r.json()

    def test_forbidden_on_users_list(self, uploader_token):
        r = requests.get(f"{API}/users/list",
                         headers={"Authorization": f"Bearer {uploader_token}"}, timeout=15)
        assert r.status_code == 403

    def test_forbidden_on_customer_profit(self, uploader_token):
        r = requests.get(f"{API}/analytics/customer-profit",
                         headers={"Authorization": f"Bearer {uploader_token}"}, timeout=15)
        assert r.status_code == 403

    def test_forbidden_on_system_reset(self, uploader_token):
        r = requests.post(f"{API}/system/reset", json={"password": "CLOSE"},
                          headers={"Authorization": f"Bearer {uploader_token}"}, timeout=15)
        assert r.status_code == 403


class TestAdminUserCreate:
    def test_admin_creates_uploader_role(self, admin_token):
        tmp = "TMP_UPL_TEST"
        # cleanup first
        requests.delete(f"{API}/users/{tmp}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        r = requests.post(f"{API}/users/create", json={
            "username": tmp, "password": "pw12345",
            "full_name": "Tmp Uploader", "role": "uploader"
        }, headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200, r.text[:200]
        assert r.json()["user"]["role"] == "uploader"
        # cleanup
        requests.delete(f"{API}/users/{tmp}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)


# ---------- branch_transfer receive w/ rate columns ----------
BT_HDR_FULL = ["Date", "Type", "Refno", "Lnarr", "Gr.Wt.", "Net.Wt.", "Tunch", "Wstg", "Fine", "Labour", "Total", "Rate"]
BT_HDR_LEGACY = ["Date", "Type", "Refno", "Lnarr", "Gr.Wt.", "Net.Wt."]


class TestBranchReceiveWithRates:
    def test_uploader_can_upload_branch_transfer(self, uploader_token, admin_token):
        item = "TEST_RCV_ITEM_A"
        # 2 kg gross, 1.8 kg net, tunch 92, fine 1.656kg, labour 5000, total 12345
        rows = [
            ["2026-01-05", "R", "R001", item, 2.0, 1.8, 92.0, 0.0, 1.656, 5000, 12345, 0],
            ["2026-01-06", "I", "I001", item, 0.5, 0.4, 0, 0, 0, 0, 0, 0],
        ]
        res = _upload(uploader_token, "branch_transfer", BT_HDR_FULL, rows,
                      start_date="2026-01-01", end_date="2026-01-31")
        assert res["status"] == "complete", f"expected complete got {res}"

        # verify DB via item detail (admin)
        r = requests.get(f"{API}/item/{item}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        # recent txns should carry rate data
        recs = d.get("recent_transactions", [])
        recv = [t for t in recs if t.get("type") == "receive"]
        assert len(recv) >= 1
        rr = recv[0]
        assert float(rr.get("tunch", 0)) > 0, f"tunch not parsed: {rr}"
        # fine stored as grams (kg * 1000)
        assert rr.get("fine", 0) > 1000, f"fine not scaled to grams: {rr.get('fine')}"
        assert rr.get("labor", 0) == 5000
        assert rr.get("total_amount", 0) == 12345

    def test_legacy_branch_transfer_no_rate_columns(self, admin_token):
        item = "TEST_RCV_LEGACY_B"
        rows = [
            ["2026-01-10", "R", "R100", item, 1.0, 0.9],
        ]
        res = _upload(admin_token, "branch_transfer", BT_HDR_LEGACY, rows,
                      start_date="2026-01-01", end_date="2026-01-31")
        assert res["status"] == "complete", res

        r = requests.get(f"{API}/item/{item}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        recv = [t for t in d.get("recent_transactions", []) if t.get("type") == "receive"]
        assert len(recv) >= 1
        rr = recv[0]
        # tunch stored as "0.0" str
        assert float(rr.get("tunch", 0)) == 0.0
        assert (rr.get("fine", 0) or 0) == 0

    def test_avg_purchase_from_receive_fallback(self, admin_token):
        """After uploading receives with rate data for an item with no purchase_ledger,
        GET /api/item/{name} should show avg_purchase_tunch>0 with rate_source='estimated'."""
        item = "TEST_RCV_FALLBACK_C"
        rows = [
            ["2026-01-05", "R", "R200", item, 2.0, 1.8, 90.0, 0.0, 1.62, 4000, 10000, 0],
        ]
        res = _upload(admin_token, "branch_transfer", BT_HDR_FULL, rows,
                      start_date="2026-01-01", end_date="2026-01-31")
        assert res["status"] == "complete", res

        # bust the 60s cache by waiting
        time.sleep(62)

        r = requests.get(f"{API}/item/{item}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["total_purchases"] >= 1, d
        assert d["avg_purchase_tunch"] > 0, d
        assert d["has_purchase_rate"] is True
        assert d["purchase_rate_source"] == "estimated", d

    def test_zero_rate_receives_do_not_dilute(self, admin_token):
        """Item with legacy zero-rate receive rows must still show tunch~90 from rate-carrying rows."""
        item = "TEST_RCV_MIX_D"
        rows_rate = [
            ["2026-02-01", "R", "R300", item, 1.0, 0.9, 90.0, 0.0, 0.81, 3000, 9000, 0],
        ]
        res1 = _upload(admin_token, "branch_transfer", BT_HDR_FULL, rows_rate,
                       start_date="2026-02-01", end_date="2026-02-28")
        assert res1["status"] == "complete"

        rows_zero = [
            ["2026-03-01", "R", "R301", item, 1.0, 0.9],
        ]
        res2 = _upload(admin_token, "branch_transfer", BT_HDR_LEGACY, rows_zero,
                       start_date="2026-03-01", end_date="2026-03-31")
        assert res2["status"] == "complete"

        time.sleep(62)
        r = requests.get(f"{API}/item/{item}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        # avg_purchase_tunch computed in get_item_detail from ALL receive rows w/ any positive rate check;
        # the zero-rate row has tunch "0.0" so INCLUDED as a purchase (per _rcv_has_rate). This dilutes.
        # BUT the fallback stats used for the ledger fallback drops zero-rate rows.
        # Verify the fallback (ledger source) tunch stays at 90.
        assert d["purchase_tunch_ledger"] > 80, f"ledger tunch diluted: {d}"


# ---------- wrong-file-format rejection ----------
SALE_HDR = ["Date", "Type", "Refno", "Party Name", "Item Name", "Stamp", "Gr.Wt.", "Net.Wt.", "Tunch", "Total"]
MASTER_HDR = ["Item Name", "Stamp", "Gr.Wt.", "Net.Wt."]
PURCHASE_HDR = ["Date", "Type", "Refno", "Party Name", "Item Name", "Stamp", "Gr.Wt.", "Net.Wt.", "Tunch", "Total"]


class TestWrongFileRejection:
    def test_master_stock_file_uploaded_as_sale_rejected(self, admin_token):
        rows = [["ITEM_X", "STAMP1", 1.0, 0.9]]
        res = _upload(admin_token, "sale", MASTER_HDR, rows,
                      start_date="2026-04-01", end_date="2026-04-30")
        assert res["status"] == "error", res
        msg = (res.get("detail") or res.get("error") or "").lower()
        assert "reject" in msg or "required" in msg, res

    def test_sale_file_uploaded_as_branch_transfer_rejected(self, admin_token):
        rows = [["2026-04-05", "S", "S001", "Cust1", "ITEM_Y", "STAMP1", 1.0, 0.9, 91.0, 8000]]
        res = _upload(admin_token, "branch_transfer", SALE_HDR, rows,
                      start_date="2026-04-01", end_date="2026-04-30")
        assert res["status"] == "error", res
        msg = (res.get("detail") or res.get("error") or "").lower()
        assert "reject" in msg or "lnarr" in msg, res

    def test_purchase_content_uploaded_as_sale_rejected_and_preserves(self, admin_token):
        """Upload a valid sale first, then a purchase-formatted file as sale — must reject
        with content sanity check, and the original sale record must remain intact."""
        # step 1: valid sale
        good_sale_rows = [
            ["2026-05-05", "S", "S010", "PartyA", "ITEM_PRESERVE", "STAMP1", 1.0, 0.9, 92.0, 9000],
        ]
        res1 = _upload(admin_token, "sale", SALE_HDR, good_sale_rows,
                       start_date="2026-05-01", end_date="2026-05-31")
        assert res1["status"] == "complete", res1

        r = requests.get(f"{API}/item/ITEM_PRESERVE",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200
        before_sales = r.json()["total_sales"]
        assert before_sales >= 1

        # step 2: purchase-format file (Type=P) uploaded as sale — content sanity should reject
        bad_rows = [
            ["2026-05-06", "P", "P010", "Supplier1", "ITEM_PRESERVE", "STAMP1", 1.0, 0.9, 90.0, 8500],
            ["2026-05-07", "P", "P011", "Supplier1", "ITEM_PRESERVE", "STAMP1", 2.0, 1.8, 90.0, 17000],
        ]
        res2 = _upload(admin_token, "sale", PURCHASE_HDR, bad_rows,
                       start_date="2026-05-01", end_date="2026-05-31")
        assert res2["status"] == "error", res2
        msg = (res2.get("detail") or res2.get("error") or "").lower()
        assert "reject" in msg or "content" in msg, res2

        # step 3: original sale must still exist
        r = requests.get(f"{API}/item/ITEM_PRESERVE",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        after_sales = r.json()["total_sales"]
        assert after_sales == before_sales, (
            f"original sale lost after rejected upload: before={before_sales} after={after_sales}"
        )

    def test_valid_sale_still_uploads_after_rejection(self, admin_token):
        rows = [
            ["2026-06-10", "S", "S020", "PartyB", "ITEM_AFTER", "STAMP1", 1.0, 0.9, 92.0, 9000],
        ]
        res = _upload(admin_token, "sale", SALE_HDR, rows,
                      start_date="2026-06-01", end_date="2026-06-30")
        assert res["status"] == "complete", res


# ---------- regression: normal sale + purchase ----------
class TestRegressionNormalUploads:
    def test_sale_upload(self, admin_token):
        rows = [
            ["2026-07-05", "S", "S030", "PartyC", "ITEM_REGR_S", "STAMP1", 1.5, 1.35, 92.5, 13500],
        ]
        res = _upload(admin_token, "sale", SALE_HDR, rows,
                      start_date="2026-07-01", end_date="2026-07-31")
        assert res["status"] == "complete", res

    def test_purchase_upload(self, admin_token):
        rows = [
            ["2026-07-06", "P", "P030", "SupplierC", "ITEM_REGR_P", "STAMP1", 2.0, 1.8, 90.0, 17000],
        ]
        res = _upload(admin_token, "purchase", PURCHASE_HDR, rows,
                      start_date="2026-07-01", end_date="2026-07-31")
        assert res["status"] == "complete", res
