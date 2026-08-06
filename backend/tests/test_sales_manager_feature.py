"""Backend tests for the new sales_manager role feature."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN = ("admin", "admin123")
SM = ("TEST_SM", "sm123")
EXEC = ("TEST_EXEC", "exec123")


def _login(u, p):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": u, "password": p}, timeout=30)
    assert r.status_code == 200, f"login failed for {u}: {r.status_code} {r.text[:300]}"
    return r.json()["access_token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def _ist_today():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def sm_token():
    return _login(*SM)


@pytest.fixture(scope="module")
def exec_token():
    return _login(*EXEC)


@pytest.fixture(scope="module")
def date_window():
    today = _ist_today()
    today_s = today.strftime("%Y-%m-%d")
    first_prev = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    earliest = min(today - timedelta(days=60), first_prev).strftime("%Y-%m-%d")
    # A safe range = last 30 days
    start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    return {"today": today_s, "earliest": earliest, "start": start, "end": today_s}


# ------- Auth & basic ----
class TestAuth:
    def test_sm_login(self, sm_token):
        assert isinstance(sm_token, str) and len(sm_token) > 10


# ------- Sales Manager Report ----
class TestSalesManagerReport:
    def test_report_shape(self, sm_token, date_window):
        r = requests.get(
            f"{BASE_URL}/api/analytics/sales-manager-report",
            params={"start_date": date_window["start"], "end_date": date_window["end"]},
            headers=_hdr(sm_token), timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert set(["period", "window", "assigned_stamps", "no_stamps_assigned",
                    "by_stamp", "by_item"]).issubset(d.keys())
        assert "totals" not in d, "totals must NOT be exposed to sales managers"
        assert d["no_stamps_assigned"] is False
        assert isinstance(d["assigned_stamps"], list) and len(d["assigned_stamps"]) >= 1
        assigned = set(d["assigned_stamps"])
        # Only assigned stamps returned in by_stamp
        for row in d["by_stamp"]:
            assert row["stamp"] in assigned, f"unexpected stamp {row['stamp']} not in {assigned}"
            assert set(row.keys()) == {"stamp", "gross_wt_kg", "net_wt_kg"}
        for row in d["by_item"]:
            assert row["stamp"] in assigned
            assert set(row.keys()) == {"item_name", "stamp", "gross_wt_kg", "net_wt_kg"}

    def test_expected_assigned_stamps(self, sm_token, date_window):
        r = requests.get(
            f"{BASE_URL}/api/analytics/sales-manager-report",
            params={"start_date": date_window["start"], "end_date": date_window["end"]},
            headers=_hdr(sm_token), timeout=60).json()
        assigned = set(r["assigned_stamps"])
        # per spec: STAMP 5, STAMP 7, Unassigned
        for expected in ["STAMP 5", "STAMP 7", "Unassigned"]:
            assert expected in assigned, f"missing {expected} in {assigned}"

    def test_date_window_start_out_of_range(self, sm_token, date_window):
        r = requests.get(
            f"{BASE_URL}/api/analytics/sales-manager-report",
            params={"start_date": "2026-01-01", "end_date": date_window["end"]},
            headers=_hdr(sm_token), timeout=30)
        assert r.status_code == 400, r.status_code

    def test_date_window_end_in_future(self, sm_token, date_window):
        future = (_ist_today() + timedelta(days=5)).strftime("%Y-%m-%d")
        r = requests.get(
            f"{BASE_URL}/api/analytics/sales-manager-report",
            params={"start_date": date_window["start"], "end_date": future},
            headers=_hdr(sm_token), timeout=30)
        assert r.status_code == 400

    def test_start_after_end(self, sm_token, date_window):
        r = requests.get(
            f"{BASE_URL}/api/analytics/sales-manager-report",
            params={"start_date": date_window["end"], "end_date": date_window["start"]},
            headers=_hdr(sm_token), timeout=30)
        assert r.status_code == 400

    def test_math_matches_admin_sales_report(self, sm_token, admin_token, date_window):
        params = {"start_date": date_window["start"], "end_date": date_window["end"]}
        sm = requests.get(f"{BASE_URL}/api/analytics/sales-manager-report",
                          params=params, headers=_hdr(sm_token), timeout=60).json()
        adm = requests.get(f"{BASE_URL}/api/analytics/sales-report",
                           params=params, headers=_hdr(admin_token), timeout=60)
        assert adm.status_code == 200, adm.text[:300]
        adm_j = adm.json()
        # Find admin's by_stamp array (name may vary)
        admin_by_stamp = None
        for key in ("by_stamp", "stamps", "stamp_wise"):
            if key in adm_j and isinstance(adm_j[key], list):
                admin_by_stamp = adm_j[key]
                break
        if admin_by_stamp is None:
            pytest.skip(f"admin sales-report has no by_stamp; keys={list(adm_j.keys())}")
        assigned = set(sm["assigned_stamps"])
        admin_filtered = [r for r in admin_by_stamp if r.get("stamp") in assigned]
        # Sum admin gross/net for assigned stamps
        def _gg(r):
            for k in ("gross_wt_kg", "gr_wt_kg", "gross_kg"):
                if k in r: return r[k]
            return 0
        def _nn(r):
            for k in ("net_wt_kg", "net_kg"):
                if k in r: return r[k]
            return 0
        admin_gross = round(sum(_gg(r) for r in admin_filtered), 3)
        admin_net = round(sum(_nn(r) for r in admin_filtered), 3)
        # Compare with SM row sums (tolerance 0.05 kg)
        sm_gross = round(sum(r["gross_wt_kg"] for r in sm["by_stamp"]), 3)
        sm_net = round(sum(r["net_wt_kg"] for r in sm["by_stamp"]), 3)
        assert abs(sm_gross - admin_gross) < 0.05, \
            f"SM gross {sm_gross} vs admin {admin_gross}"
        assert abs(sm_net - admin_net) < 0.05, \
            f"SM net {sm_net} vs admin {admin_net}"


# ------- Role gates ----
class TestRoleGates:
    def test_exec_forbidden_from_sm_report(self, exec_token, date_window):
        r = requests.get(
            f"{BASE_URL}/api/analytics/sales-manager-report",
            params={"start_date": date_window["start"], "end_date": date_window["end"]},
            headers=_hdr(exec_token), timeout=30)
        assert r.status_code == 403

    def test_sm_can_access_polythene_all(self, sm_token):
        r = requests.get(f"{BASE_URL}/api/polythene/all", headers=_hdr(sm_token), timeout=30)
        assert r.status_code == 200, r.text[:200]

    def test_sm_forbidden_from_approvals(self, sm_token):
        r1 = requests.get(f"{BASE_URL}/api/manager/pending-approvals", headers=_hdr(sm_token), timeout=30)
        r2 = requests.get(f"{BASE_URL}/api/manager/all-entries", headers=_hdr(sm_token), timeout=30)
        assert r1.status_code == 403, r1.status_code
        assert r2.status_code == 403, r2.status_code

    def test_sm_can_post_executive_stock_entry(self, sm_token):
        # Minimum realistic payload — endpoint should not 403 for sales_manager
        # We'll do a dry-invalid payload; expect NOT 403 (either 200/201/400/422)
        r = requests.post(f"{BASE_URL}/api/executive/stock-entry",
                          json={}, headers=_hdr(sm_token), timeout=30)
        assert r.status_code != 403, f"sales_manager should have exec powers, got 403"


# ------- Admin user CRUD for sales_manager role ----
class TestSalesManagerUserAdmin:
    tmp_user = "TMP_SM_TEST"
    tmp_no_stamp_user = "TMP_SM_NOSTAMP"

    def test_create_sales_manager(self, admin_token):
        # cleanup pre-existing
        requests.delete(f"{BASE_URL}/api/users/{self.tmp_user}", headers=_hdr(admin_token), timeout=30)
        r = requests.post(f"{BASE_URL}/api/users/create",
                          json={"username": self.tmp_user, "password": "tmp12345",
                                "role": "sales_manager", "full_name": "Tmp SM"},
                          headers=_hdr(admin_token), timeout=30)
        assert r.status_code in (200, 201), r.text[:300]

    def test_update_user_role_to_sales_manager(self, admin_token):
        # First create with another role, then update
        uname = "TMP_SM_UPD"
        requests.delete(f"{BASE_URL}/api/users/{uname}", headers=_hdr(admin_token), timeout=30)
        c = requests.post(f"{BASE_URL}/api/users/create",
                          json={"username": uname, "password": "tmp12345",
                                "role": "manager", "full_name": "Upd"},
                          headers=_hdr(admin_token), timeout=30)
        assert c.status_code in (200, 201), c.text[:300]
        u = requests.put(f"{BASE_URL}/api/users/{uname}",
                         json={"role": "sales_manager"},
                         headers=_hdr(admin_token), timeout=30)
        assert u.status_code == 200, u.text[:300]
        requests.delete(f"{BASE_URL}/api/users/{uname}", headers=_hdr(admin_token), timeout=30)

    def test_no_stamps_assigned_flag(self, admin_token, date_window):
        # Create throwaway sales_manager, login, call endpoint
        requests.delete(f"{BASE_URL}/api/users/{self.tmp_no_stamp_user}", headers=_hdr(admin_token), timeout=30)
        c = requests.post(f"{BASE_URL}/api/users/create",
                          json={"username": self.tmp_no_stamp_user, "password": "nostamp1",
                                "role": "sales_manager", "full_name": "NoStamp"},
                          headers=_hdr(admin_token), timeout=30)
        assert c.status_code in (200, 201), c.text[:300]
        tok = _login(self.tmp_no_stamp_user, "nostamp1")
        r = requests.get(f"{BASE_URL}/api/analytics/sales-manager-report",
                         params={"start_date": date_window["start"], "end_date": date_window["end"]},
                         headers=_hdr(tok), timeout=30).json()
        assert r["no_stamps_assigned"] is True
        assert r["by_stamp"] == [] and r["by_item"] == []
        assert "totals" not in r
        requests.delete(f"{BASE_URL}/api/users/{self.tmp_no_stamp_user}",
                        headers=_hdr(admin_token), timeout=30)

    def test_zzz_cleanup(self, admin_token):
        for u in [self.tmp_user, self.tmp_no_stamp_user, "TMP_SM_UPD"]:
            requests.delete(f"{BASE_URL}/api/users/{u}", headers=_hdr(admin_token), timeout=30)
