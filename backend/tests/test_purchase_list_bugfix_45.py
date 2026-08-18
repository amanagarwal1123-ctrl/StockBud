"""Iteration 45 – Bug-fix verification for purchase list empty-state / cache guard."""
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


# 1) Basic regression: non-empty rows + window_txn_count present
def test_purchase_list_returns_rows_and_window_txn_count(admin_headers):
    r = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=90)
    assert r.status_code == 200, r.text[:400]
    d = r.json()
    assert "window_txn_count" in d, "window_txn_count field missing"
    assert isinstance(d["window_txn_count"], int)
    assert d["window_txn_count"] > 0, f"window_txn_count should be > 0, got {d['window_txn_count']}"
    assert len(d["rows"]) > 0, "purchase-list returned zero rows (regression!)"
    # Was ~298 in iteration 44
    assert len(d["rows"]) >= 100, f"row count regressed: {len(d['rows'])}"
    print(f"rows={len(d['rows'])} window_txn_count={d['window_txn_count']}")


# 2) Cached-empty snapshot must be bypassed and recomputed
def test_empty_cached_snapshot_is_bypassed(admin_headers):
    r = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=90)
    assert r.status_code == 200
    d = r.json()
    date_s = d["date"]
    original_row_count = len(d["rows"])
    assert original_row_count > 0

    async def poison():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        snap = await db.purchase_list_snapshots.find_one({"date": date_s})
        assert snap, "no snapshot exists for today"
        # Preserve fingerprint & baseline_start but nuke rows
        await db.purchase_list_snapshots.update_one(
            {"date": date_s},
            {"$set": {"rows": []}},
        )
        # Confirm
        after = await db.purchase_list_snapshots.find_one({"date": date_s})
        assert after["rows"] == []
        assert after.get("fingerprint") == snap.get("fingerprint")
        client.close()

    asyncio.run(poison())

    # Now GET should recompute (not serve the empty cache)
    r2 = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=90)
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["rows"]) > 0, "empty cached snapshot was served (guard broken)"
    assert len(d2["rows"]) == original_row_count, \
        f"row count mismatch after recompute: {len(d2['rows'])} vs {original_row_count}"

    # And the snapshot in mongo should now be repopulated
    async def verify():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        snap = await db.purchase_list_snapshots.find_one({"date": date_s})
        assert snap["rows"], "snapshot rows still empty after recompute"
        client.close()

    asyncio.run(verify())


# 3) POST /purchase-list/orderers → new orderer visible in list
def test_create_and_delete_empty_qa_orderer(admin_headers):
    name = "EMPTY_QA"
    r = requests.post(f"{API}/purchase-list/orderers", headers=admin_headers,
                      json={"name": name}, timeout=30)
    assert r.status_code == 200, r.text[:400]

    d = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60).json()
    assert name in d["orderers"]

    # cleanup via mongo
    async def cleanup():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        await db.purchase_orderers.delete_one({"name": name})
        client.close()

    asyncio.run(cleanup())
    d2 = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=60).json()
    assert name not in d2["orderers"], "EMPTY_QA cleanup failed"
