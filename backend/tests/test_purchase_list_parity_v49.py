"""v49: Purchase List <-> Current Stock engine parity (chained mapping bug) + v4 fingerprints."""
import os
from collections import defaultdict

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"admin login failed {r.status_code}: {r.text[:300]}")
    tok = r.json().get("access_token")
    assert tok, "no access_token"
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def purchase_list(client):
    r = client.get(f"{BASE_URL}/api/purchase-list", timeout=300)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="module")
def engine_inv(client):
    r = client.get(f"{BASE_URL}/api/inventory/current", timeout=300)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    return r.json()


# --- module: purchase_list_service engine-direct current stock ---
def test_every_row_matches_engine_stock(purchase_list, engine_inv):
    rows = purchase_list.get("rows") or purchase_list.get("items") or []
    assert rows, f"no rows in purchase-list response keys={list(purchase_list.keys())}"
    mem2leader = {}
    for row in rows:
        for m in row.get("members", []):
            mem2leader[m["name"].strip()] = row["item_name"]
    eng = defaultdict(float)
    for si in engine_inv.get("stamp_items", []):
        raw = (si.get("item_name") or "").strip()
        if not raw or raw.isdigit():
            continue
        leader = mem2leader.get(raw)
        if leader:
            eng[leader] += si.get("net_wt", 0) or 0
    mismatches = []
    for row in rows:
        expected = eng.get(row["item_name"], 0.0) / 1000.0
        if abs(expected - row["current_stock_kg"]) > 0.002:
            mismatches.append((row["item_name"], row["current_stock_kg"], round(expected, 3)))
    assert not mismatches, f"{len(mismatches)}/{len(rows)} mismatched: {mismatches[:10]}"


def test_jb70_kada_chain_merged(purchase_list):
    rows = purchase_list.get("rows") or []
    leaders = [r["item_name"] for r in rows]
    assert "JB-70 KADA II" not in leaders, "phantom chained row still present"
    target = [r for r in rows if r["item_name"] == "JB-70 KADA"]
    assert target, f"JB-70 KADA row missing. sample leaders={leaders[:5]}"
    row = target[0]
    assert abs(row["current_stock_kg"] - 4.180) < 0.002, row["current_stock_kg"]
    mem = {m["name"]: m["current_stock_kg"] for m in row.get("members", [])}
    assert "JB-70 KADA II" in mem and "JB-70 KADA" in mem, mem
    assert abs(mem["JB-70 KADA II"] - 17.139) < 0.002, mem
    assert abs(mem["JB-70 KADA"] - (-12.959)) < 0.002, mem


def test_row_members_sum_to_row_stock(purchase_list):
    rows = purchase_list.get("rows") or []
    bad = []
    for r in rows:
        if not r.get("members"):
            continue
        s = sum(m["current_stock_kg"] for m in r["members"])
        if abs(s - r["current_stock_kg"]) > 0.005:
            bad.append((r["item_name"], r["current_stock_kg"], round(s, 3)))
    assert not bad, bad[:10]


# --- module: server._purchase_fingerprint / opening cache (v4) ---
def test_fingerprints_are_v4(purchase_list):
    import asyncio
    asyncio.run(_check_fingerprints())


async def _check_fingerprints():
    from motor.motor_asyncio import AsyncIOMotorClient
    env = dotenv_values("/app/backend/.env")
    cl = AsyncIOMotorClient(env["MONGO_URL"])
    db = cl[env["DB_NAME"]]
    try:
        snaps = await db.purchase_list_snapshots.find({}, {"_id": 0, "date": 1, "fingerprint": 1}).sort("date", -1).to_list(3)
        assert snaps, "no purchase_list_snapshots docs"
        assert snaps[0]["fingerprint"].startswith("v4:"), snaps[0]
        caches = await db.purchase_opening_cache.find({}, {"_id": 0, "date": 1, "fingerprint": 1}).sort("date", -1).to_list(3)
        assert caches, "no purchase_opening_cache docs"
        assert caches[0]["fingerprint"].startswith("v4:"), caches[0]
    finally:
        cl.close()
