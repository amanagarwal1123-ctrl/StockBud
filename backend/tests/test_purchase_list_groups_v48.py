"""Iteration 48 – group-aware purchase list: members array, profit_silver_tunch,
v2 fingerprints (snapshot + opening cache) and group-edit cache invalidation."""
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


def _get_loop():
    """Reusable event loop (_get_loop() raises on py3.11 when unset/closed)."""
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def _login(u, p):
    r = requests.post(f"{API}/auth/login", json={"username": u, "password": p}, timeout=30)
    assert r.status_code == 200, r.text[:400]
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin', 'admin123')}"}


@pytest.fixture(scope="module")
def plist(admin_headers):
    r = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=180)
    assert r.status_code == 200, r.text[:400]
    return r.json()


def _mongo():
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


# ---- rows / sorting / members ----
class TestGroupAwareRows:
    def test_sorted_by_profit_silver_tunch_desc_nulls_last(self, plist):
        rows = plist["rows"]
        assert len(rows) > 0
        keys = [(r.get("profit_silver_tunch") is None, -(r.get("profit_silver_tunch") or 0)) for r in rows]
        assert keys == sorted(keys), f"not sorted: first 10 = {[r.get('profit_silver_tunch') for r in rows[:10]]}"

    def test_tunch_equals_per_kg_over_ten(self, plist):
        bad = []
        for r in plist["rows"]:
            t, p = r.get("profit_silver_tunch"), r.get("profit_silver_per_kg")
            if t is not None and p is not None and abs(t - p / 10.0) > 0.06:
                bad.append((r["item_name"], t, p))
        assert not bad, f"mismatched tunch vs per_kg: {bad[:5]}"

    def test_every_row_has_members_array(self, plist):
        rows = plist["rows"]
        missing = [r["item_name"] for r in rows if not isinstance(r.get("members"), list)]
        assert not missing, f"rows without members list: {missing[:5]}"
        for r in rows:
            for m in r["members"]:
                assert set(["name", "current_stock_kg", "sold_60d_kg"]).issubset(m.keys()), m

    def test_grouped_leaders_present_with_two_members(self, plist):
        byname = {r["item_name"]: r for r in plist["rows"]}
        expected = ["KADA-AS 70", "TULSI 70 -264", "SNT 40-256"]
        found = {}
        for name in expected:
            if name in byname:
                found[name] = byname[name]
        assert found, f"none of the grouped leaders found. rows={list(byname)[:20]}"
        for name, row in found.items():
            assert len(row["members"]) >= 2, f"{name} has members {row['members']}"
            for m in row["members"]:
                assert isinstance(m["current_stock_kg"], (int, float))
                assert isinstance(m["sold_60d_kg"], (int, float))
            s = sum(m["current_stock_kg"] for m in row["members"])
            assert abs(s - row["current_stock_kg"]) <= 0.005, \
                f"{name}: member sum {s} != leader {row['current_stock_kg']}"
        # all 3 preview leaders expected
        assert len(found) == 3, f"expected 3 grouped leaders, found {list(found)}"

    def test_member_names_not_separate_rows(self, plist):
        names = {r["item_name"] for r in plist["rows"]}
        for member in ["SNT-40 PREMIUM", "KADA AS 70 FANCY"]:
            assert member not in names, f"{member} appears as its own row"

    def test_member_sum_consistency_all_multi_member_rows(self, plist):
        """Reports how many rows still show negative stock (informational) and asserts
        leader stock == sum(member stock) for every multi-member row."""
        rows = plist["rows"]
        neg = [r["item_name"] for r in rows if r["current_stock_kg"] < 0]
        print(f"INFO: {len(neg)}/{len(rows)} rows have negative current_stock_kg (e.g. {neg[:5]})")
        for r in rows:
            mems = r.get("members") or []
            if len(mems) > 1:
                s = sum(m["current_stock_kg"] for m in mems)
                assert abs(s - r["current_stock_kg"]) <= 0.005, (r["item_name"], s, r["current_stock_kg"])


# ---- fingerprints + cache invalidation ----
class TestCacheV2:
    def test_snapshot_and_opening_cache_fingerprints_are_v2(self, plist):
        async def _run():
            db = _mongo()
            snaps = await db.purchase_list_snapshots.find({}, {"_id": 0, "date": 1, "fingerprint": 1}).to_list(None)
            opens = await db.purchase_opening_cache.find({}, {"_id": 0, "date": 1, "fingerprint": 1}).to_list(None)
            return snaps, opens
        snaps, opens = _get_loop().run_until_complete(_run())
        assert snaps, "no purchase_list_snapshots docs"
        latest = sorted(snaps, key=lambda s: s["date"])[-1]
        assert latest["fingerprint"].startswith("v4:"), latest
        assert opens, "no purchase_opening_cache docs"
        assert any(o["fingerprint"].startswith("v4:") for o in opens), opens

    def test_group_edit_invalidates_snapshot(self, admin_headers, plist):
        async def _read(db_state=None):
            db = _mongo()
            snaps = await db.purchase_list_snapshots.find({}, {"_id": 0}).to_list(None)
            latest = sorted(snaps, key=lambda s: s["date"])[-1]
            return latest["date"], latest["fingerprint"], latest.get("computed_at")

        async def _insert():
            db = _mongo()
            await db.item_groups.insert_one({"group_name": "QA_TMP_GROUP", "members": ["QA_TMP_GROUP"]})

        async def _delete():
            db = _mongo()
            await db.item_groups.delete_many({"group_name": "QA_TMP_GROUP"})

        loop = _get_loop()
        date0, fp0, ca0 = loop.run_until_complete(_read())
        try:
            loop.run_until_complete(_insert())
            r = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=240)
            assert r.status_code == 200, r.text[:300]
            date1, fp1, ca1 = loop.run_until_complete(_read())
            assert fp1 != fp0, f"fingerprint unchanged after group insert: {fp0}"
            assert ca1 > ca0, f"computed_at not newer: {ca0} -> {ca1}"
            assert fp1.startswith("v4:")
        finally:
            loop.run_until_complete(_delete())
            r = requests.get(f"{API}/purchase-list", headers=admin_headers, timeout=240)
            assert r.status_code == 200
            date2, fp2, ca2 = loop.run_until_complete(_read())
            assert fp2 == fp0, f"fingerprint not restored: {fp0} vs {fp2}"
