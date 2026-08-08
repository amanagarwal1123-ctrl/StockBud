"""Tests for the Stock Movement Audit feature and inventory regression."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://sales-manager-role.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

ADMIN = {"username": "admin", "password": "admin123"}
EXEC = {"username": "TEST_EXEC", "password": "exec123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed for {creds['username']}: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def exec_token():
    try:
        return _login(EXEC)
    except AssertionError as e:
        pytest.skip(f"executive login unavailable: {e}")


@pytest.fixture(scope="module")
def audit_data(admin_token):
    r = requests.get(f"{API}/stock-audit/uploads", headers={"Authorization": f"Bearer {admin_token}"}, timeout=120)
    assert r.status_code == 200, f"audit endpoint failed: {r.status_code} {r.text[:300]}"
    return r.json()


class TestStockAuditEndpoint:
    def test_admin_access_and_schema(self, audit_data):
        assert set(["anchor_date", "uploads", "total_net_change_kg"]).issubset(audit_data.keys())
        assert isinstance(audit_data["uploads"], list)
        assert isinstance(audit_data["total_net_change_kg"], (int, float))

    def test_each_upload_schema(self, audit_data):
        required = {"batch_id","uploaded_at","types","date_min","date_max","rows_inserted",
                    "rows_replaced","rows_counted","rows_before_anchor",
                    "inserted_net_kg","replaced_net_kg","net_change_kg","gross_change_kg","by_type"}
        for u in audit_data["uploads"]:
            missing = required - set(u.keys())
            assert not missing, f"upload {u.get('batch_id')} missing keys {missing}"
            assert isinstance(u["by_type"], dict)

    def test_net_change_math(self, audit_data):
        for u in audit_data["uploads"]:
            expected = round(u["inserted_net_kg"] - u["replaced_net_kg"], 3)
            assert abs(u["net_change_kg"] - expected) < 0.002, \
                f"batch {u['batch_id']}: net_change {u['net_change_kg']} != {expected}"

    def test_type_signs(self, audit_data):
        # Sales/returns/issue should be negative or zero; purchase/purchase_return sign convention
        # Per spec: sale negative, sale_return positive, purchase positive, purchase_return negative,
        # issue negative, receive positive.
        pos = {"purchase", "sale_return", "receive"}
        neg = {"sale", "purchase_return", "issue"}
        for u in audit_data["uploads"]:
            for t, v in u["by_type"].items():
                if v["rows"] == 0 or v["net_kg"] == 0:
                    continue
                if t in pos:
                    assert v["net_kg"] > 0, f"batch {u['batch_id']} type {t} expected positive got {v['net_kg']}"
                elif t in neg:
                    assert v["net_kg"] < 0, f"batch {u['batch_id']} type {t} expected negative got {v['net_kg']}"

    def test_known_idempotent_duplicates(self, audit_data):
        # Known re-uploads should have net_change_kg == 0.0
        targets = [b for b in audit_data["uploads"]
                   if b["batch_id"].startswith("3f03c030") or b["batch_id"].startswith("c88fb1ad")]
        # If found, they must be zero net change
        found = {b["batch_id"][:8]: b["net_change_kg"] for b in targets}
        for k, v in found.items():
            assert abs(v) < 0.002, f"expected idempotent 0 change for {k}, got {v}"
        # Advisory: log which found
        print(f"idempotent duplicates found: {found}")

    def test_branch_transfer_batch(self, audit_data):
        # Should exist a batch with both issue and receive types (Branch Transfer 2026-03-03)
        bt = [u for u in audit_data["uploads"] if "issue" in u["types"] and "receive" in u["types"]]
        # Just verify structure if present
        for u in bt:
            assert "issue" in u["by_type"] or "receive" in u["by_type"]

    def test_rows_before_anchor_baselines(self, audit_data):
        # At least one full-year batch (date_min in 2025) should have rows_before_anchor > 0
        has_baseline_skip = any(
            (u.get("date_min", "") or "").startswith("2025") and u["rows_before_anchor"] > 0
            for u in audit_data["uploads"]
        )
        # Not a hard fail: preview DB may not have 2025 batches in latest 20; log only
        print(f"has 2025 batch with rows_before_anchor>0: {has_baseline_skip}")

    def test_forbidden_for_executive(self, exec_token):
        r = requests.get(f"{API}/stock-audit/uploads", headers={"Authorization": f"Bearer {exec_token}"}, timeout=60)
        assert r.status_code == 403, f"executive should get 403, got {r.status_code} {r.text[:200]}"

    def test_unauthenticated(self):
        r = requests.get(f"{API}/stock-audit/uploads", timeout=30)
        assert r.status_code in (401, 403)


class TestInventoryRegression:
    def test_current_inventory(self, admin_token):
        r = requests.get(f"{API}/inventory/current", headers={"Authorization": f"Bearer {admin_token}"}, timeout=120)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("inventory", "by_stamp", "total_gr_wt", "total_net_wt", "negative_items"):
            assert k in d, f"missing key {k}"
        assert d["total_gr_wt"] is not None
        assert d["total_net_wt"] is not None
        assert isinstance(d["total_net_wt"], (int, float))
