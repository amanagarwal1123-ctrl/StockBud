"""v50: Orderer management (rename/delete + reassign) on the admin Purchase List."""
import os
import pytest
import requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api"

SPLIT = "QA_SPLIT"
SPLIT2 = "QA_SPLIT2"


def _login(u, p):
    r = requests.post(f"{API}/auth/login", json={"username": u, "password": p}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"login {u} failed {r.status_code}: {r.text[:300]}")
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('admin', 'admin123')}"})
    return s


@pytest.fixture(scope="module")
def execu():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {_login('TEST_EXEC', 'exec123')}"})
    return s


@pytest.fixture(scope="module")
def pl(admin):
    r = admin.get(f"{API}/purchase-list", timeout=180)
    assert r.status_code == 200, r.text[:300]
    return r.json()


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin, pl):
    yield
    # restore any QA_* orderers away
    r = admin.get(f"{API}/purchase-list", timeout=180)
    if r.status_code == 200:
        for o in r.json().get("orderers", []):
            if o.startswith("QA_"):
                admin.delete(f"{API}/purchase-list/orderers/{o}", params={"reassign_to": "Admin"}, timeout=60)


# --- happy path: create -> assign item -> rename -> delete+reassign ---
class TestOrdererLifecycle:
    def test_lifecycle(self, admin, pl):
        rows = pl["rows"]
        assert rows, "purchase list has no rows to test with"
        item = rows[0]["item_name"]
        orig_purview = rows[0].get("purview", "Admin")

        # create
        r = admin.post(f"{API}/purchase-list/orderers", json={"name": SPLIT}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["name"] == SPLIT

        # assign item
        r = admin.post(f"{API}/purchase-list/item-state",
                       json={"item_name": item, "purview": SPLIT}, timeout=60)
        assert r.status_code == 200, r.text[:300]

        # rename
        r = admin.put(f"{API}/purchase-list/orderers/{SPLIT}", json={"new_name": SPLIT2}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["name"] == SPLIT2
        assert body["items_moved"] >= 1, body

        pl2 = admin.get(f"{API}/purchase-list", timeout=180).json()
        assert SPLIT2 in pl2["orderers"]
        assert SPLIT not in pl2["orderers"]
        row = next(x for x in pl2["rows"] if x["item_name"] == item)
        assert row["purview"] == SPLIT2, row

        # delete + reassign
        r = admin.delete(f"{API}/purchase-list/orderers/{SPLIT2}",
                         params={"reassign_to": "Admin"}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body["items_reassigned"] >= 1, body
        assert body["reassigned_to"] == "Admin"

        pl3 = admin.get(f"{API}/purchase-list", timeout=180).json()
        assert SPLIT2 not in pl3["orderers"]
        row = next(x for x in pl3["rows"] if x["item_name"] == item)
        assert row["purview"] == "Admin", row

        # restore original purview
        admin.post(f"{API}/purchase-list/item-state",
                   json={"item_name": item, "purview": orig_purview}, timeout=60)


# --- guards ---
class TestGuards:
    def test_rename_admin_400(self, admin):
        r = admin.put(f"{API}/purchase-list/orderers/Admin", json={"new_name": "X"}, timeout=60)
        assert r.status_code == 400, r.text[:200]

    def test_delete_admin_400(self, admin):
        r = admin.delete(f"{API}/purchase-list/orderers/Admin", timeout=60)
        assert r.status_code == 400, r.text[:200]

    def test_rename_to_admin_400(self, admin):
        admin.post(f"{API}/purchase-list/orderers", json={"name": "QA_G1"}, timeout=60)
        r = admin.put(f"{API}/purchase-list/orderers/QA_G1", json={"new_name": "admin"}, timeout=60)
        assert r.status_code == 400, r.text[:200]

    def test_rename_unknown_404(self, admin):
        r = admin.put(f"{API}/purchase-list/orderers/QA_NOPE", json={"new_name": "QA_NOPE2"}, timeout=60)
        assert r.status_code == 404, r.text[:200]

    def test_delete_unknown_404(self, admin):
        r = admin.delete(f"{API}/purchase-list/orderers/QA_NOPE", timeout=60)
        assert r.status_code == 404, r.text[:200]

    def test_rename_duplicate_400(self, admin):
        admin.post(f"{API}/purchase-list/orderers", json={"name": "QA_G1"}, timeout=60)
        admin.post(f"{API}/purchase-list/orderers", json={"name": "QA_G2"}, timeout=60)
        r = admin.put(f"{API}/purchase-list/orderers/QA_G1", json={"new_name": "QA_G2"}, timeout=60)
        assert r.status_code == 400, r.text[:200]

    def test_rename_empty_400(self, admin):
        r = admin.put(f"{API}/purchase-list/orderers/QA_G1", json={"new_name": "  "}, timeout=60)
        assert r.status_code == 400, r.text[:200]

    def test_delete_reassign_to_self_400(self, admin):
        r = admin.delete(f"{API}/purchase-list/orderers/QA_G1",
                         params={"reassign_to": "QA_G1"}, timeout=60)
        assert r.status_code == 400, r.text[:200]

    def test_delete_reassign_unknown_target_400(self, admin):
        r = admin.delete(f"{API}/purchase-list/orderers/QA_G1",
                         params={"reassign_to": "QA_NOPE"}, timeout=60)
        assert r.status_code == 400, r.text[:200]

    def test_non_admin_403(self, execu):
        r = execu.put(f"{API}/purchase-list/orderers/QA_G1", json={"new_name": "QA_G9"}, timeout=60)
        assert r.status_code == 403, r.text[:200]
        r = execu.delete(f"{API}/purchase-list/orderers/QA_G1", timeout=60)
        assert r.status_code == 403, r.text[:200]

    def test_unauth_401(self):
        r = requests.put(f"{API}/purchase-list/orderers/QA_G1", json={"new_name": "QA_G9"}, timeout=60)
        assert r.status_code in (401, 403), r.status_code

    def test_cleanup_guard_orderers(self, admin):
        for n in ("QA_G1", "QA_G2"):
            r = admin.delete(f"{API}/purchase-list/orderers/{n}",
                             params={"reassign_to": "Admin"}, timeout=60)
            assert r.status_code in (200, 404), r.text[:200]
