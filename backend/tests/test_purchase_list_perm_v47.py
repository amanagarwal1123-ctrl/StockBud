"""Iteration 47 – perm_removed (permanent delete) + opening cache tests."""
import os
import asyncio
import pytest
import requests
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

frontend_env = dotenv_values("/app/frontend/.env")
backend_env = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = backend_env.get("MONGO_URL")
DB_NAME = backend_env.get("DB_NAME")


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


def _get_list(hdrs):
    r = requests.get(f"{API}/purchase-list", headers=hdrs, timeout=90)
    assert r.status_code == 200, r.text[:400]
    return r.json()


# ---- deleted-items endpoint ----
class TestPermRemoved:
    def test_non_admin_forbidden_on_deleted_items(self, exec_headers):
        r = requests.get(f"{API}/purchase-list/deleted-items", headers=exec_headers, timeout=30)
        assert r.status_code == 403

    def test_perm_remove_flow_and_refresh_does_not_restore(self, admin_headers):
        d = _get_list(admin_headers)
        assert len(d["rows"]) >= 2
        # pick an item that is not GOBI PAYAL / has no green mark
        candidate = None
        for r in d["rows"]:
            if r["item_name"].startswith("GOBI PAYAL"):
                continue
            if r.get("green") or r.get("temp_removed") or r.get("perm_removed"):
                continue
            candidate = r["item_name"]
            break
        assert candidate, "no candidate item"
        try:
            # perm_removed=true
            r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                              json={"item_name": candidate, "perm_removed": True}, timeout=30)
            assert r.status_code == 200

            # Row present with perm_removed True
            d2 = _get_list(admin_headers)
            row = next((r for r in d2["rows"] if r["item_name"] == candidate), None)
            assert row is not None, "row should still be present in /purchase-list (frontend filters it)"
            assert row["perm_removed"] is True

            # Appears in deleted-items
            r = requests.get(f"{API}/purchase-list/deleted-items", headers=admin_headers, timeout=30)
            assert r.status_code == 200
            names = [i["item_name"] for i in r.json()["items"]]
            assert candidate in names

            # Refresh should NOT clear perm_removed
            r = requests.post(f"{API}/purchase-list/refresh", headers=admin_headers, timeout=30)
            assert r.status_code == 200
            r = requests.get(f"{API}/purchase-list/deleted-items", headers=admin_headers, timeout=30)
            assert candidate in [i["item_name"] for i in r.json()["items"]]

            # perm_removed=false restores
            r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                              json={"item_name": candidate, "perm_removed": False}, timeout=30)
            assert r.status_code == 200
            r = requests.get(f"{API}/purchase-list/deleted-items", headers=admin_headers, timeout=30)
            assert candidate not in [i["item_name"] for i in r.json()["items"]]
            d3 = _get_list(admin_headers)
            row = next((r for r in d3["rows"] if r["item_name"] == candidate), None)
            assert row is not None
            assert row["perm_removed"] is False
        finally:
            requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": candidate, "perm_removed": False}, timeout=30)

    def test_refresh_still_clears_temp_removed(self, admin_headers):
        d = _get_list(admin_headers)
        candidate = None
        for r in d["rows"]:
            if r["item_name"].startswith("GOBI PAYAL"):
                continue
            if r.get("green") or r.get("temp_removed") or r.get("perm_removed"):
                continue
            candidate = r["item_name"]
            break
        assert candidate
        try:
            r = requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                              json={"item_name": candidate, "temp_removed": True}, timeout=30)
            assert r.status_code == 200
            d2 = _get_list(admin_headers)
            row = next(r for r in d2["rows"] if r["item_name"] == candidate)
            assert row["temp_removed"] is True

            r = requests.post(f"{API}/purchase-list/refresh", headers=admin_headers, timeout=30)
            assert r.status_code == 200 and r.json().get("restored", 0) >= 1
            d3 = _get_list(admin_headers)
            row = next(r for r in d3["rows"] if r["item_name"] == candidate)
            assert row["temp_removed"] is False
        finally:
            requests.post(f"{API}/purchase-list/item-state", headers=admin_headers,
                          json={"item_name": candidate, "temp_removed": False}, timeout=30)


# ---- opening cache ----
class TestOpeningCache:
    def test_opening_cache_exists_and_survives_snapshot_delete(self, admin_headers):
        # Warm up
        d = _get_list(admin_headers)
        assert len(d["rows"]) > 0
        original_row_count = len(d["rows"])
        baseline_start = d["baseline_start"]  # e.g. 2026-01-01
        # baseline_start - 1 day
        from datetime import datetime, timedelta
        bs = datetime.strptime(baseline_start, "%Y-%m-%d").date()
        opening_key = (bs - timedelta(days=1)).strftime("%Y-%m-%d")

        async def read_cache():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            docs = await db.purchase_opening_cache.find({}, {"_id": 0}).to_list(length=50)
            client.close()
            return docs

        docs_before = asyncio.run(read_cache())
        assert docs_before, "purchase_opening_cache collection has no docs"
        # find opening doc
        opening_doc = next((d for d in docs_before if d.get("date") == opening_key
                            or d.get("as_of_date") == opening_key
                            or d.get("opening_date") == opening_key
                            or d.get("_key") == opening_key), None)
        # if not keyed by date field, just pick the first (baseline_start-1) doc — accept any
        if not opening_doc:
            opening_doc = docs_before[0]
        assert "fingerprint" in opening_doc, f"missing fingerprint field: {list(opening_doc.keys())}"
        assert "entries" in opening_doc or "opening" in opening_doc or "rows" in opening_doc, \
            f"missing entries field: {list(opening_doc.keys())}"
        computed_at_before = opening_doc.get("computed_at")

        # nuke all purchase_list_snapshots
        async def nuke():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.purchase_list_snapshots.delete_many({})
            client.close()
        asyncio.run(nuke())

        # GET should still be fast + full rows, opening cache untouched
        import time as _t
        t0 = _t.time()
        d2 = _get_list(admin_headers)
        dur = _t.time() - t0
        assert len(d2["rows"]) == original_row_count, \
            f"row count mismatch after snapshot nuke: {len(d2['rows'])} vs {original_row_count}"
        print(f"Recompute took {dur:.2f}s with opening cache warm")

        docs_after = asyncio.run(read_cache())
        opening_doc_after = next((d for d in docs_after
                                  if d.get("fingerprint") == opening_doc.get("fingerprint")), None)
        assert opening_doc_after, "opening cache doc missing after recompute"
        assert opening_doc_after.get("computed_at") == computed_at_before, \
            "opening cache was recomputed (computed_at changed) — cache miss"
