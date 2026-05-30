"""
Tests for monthly_summary freshness machinery.

These guard the regression that motivated the change: pre-computed summaries
served stale numbers after an upload because the background recompute was
fire-and-forget and silently failed. Now ``ensure_year_summary_fresh`` does
a synchronous recompute if the live transaction fingerprint diverges from
the stored ``_meta`` doc.
"""
import asyncio
import os
import sys
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.monthly_summary_service import (
    ensure_year_summary_fresh,
    get_year_meta,
    is_year_summary_stale,
    recompute_monthly_summaries,
)


MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_BASE = os.environ.get('DB_NAME', 'test_db')


def _run(coro):
    """Run an async coroutine to completion (avoids pytest-asyncio dependency)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fresh_db():
    """Return an isolated test database connection scoped to this run."""
    client = AsyncIOMotorClient(MONGO_URL)
    name = f"{DB_BASE}_fresh_{uuid.uuid4().hex[:8]}"
    db = client[name]
    return client, db


async def _drop(client, db):
    await client.drop_database(db.name)
    client.close()


async def _seed_txn(db, item, date, t_type, net_wt_g, total, created_at):
    await db.transactions.insert_one({
        "item_name": item, "date": date, "type": t_type,
        "net_wt": net_wt_g, "gr_wt": net_wt_g, "fine": net_wt_g * 0.65,
        "tunch": 65.0, "total_amount": total, "labor": total,
        "party_name": "Test Party", "batch_id": "b1",
        "created_at": created_at,
    })


def test_meta_doc_written_after_recompute():
    async def _t():
        client, db = _fresh_db()
        try:
            await _seed_txn(db, "JB-70 RING", "2026-04-10", "sale", 1000, 50000,
                            "2026-04-10T10:00:00+00:00")
            await db.master_items.insert_one({"item_name": "JB-70 RING", "stamp": "STAMP1"})
            await recompute_monthly_summaries(db, 2026)
            meta = await get_year_meta(db, 2026)
            assert meta is not None
            assert meta["year"] == 2026
            assert meta["summary_type"] == "_meta"
            assert meta["txn_count"] == 1
            assert meta["max_created_at"] == "2026-04-10T10:00:00+00:00"
            assert "computed_at" in meta
        finally:
            await _drop(client, db)
    _run(_t())


def test_is_stale_detects_new_transaction():
    async def _t():
        client, db = _fresh_db()
        try:
            await _seed_txn(db, "JB-70 RING", "2026-04-10", "sale", 1000, 50000,
                            "2026-04-10T10:00:00+00:00")
            await recompute_monthly_summaries(db, 2026)
            assert (await is_year_summary_stale(db, 2026)) is False
            await _seed_txn(db, "VS-70 PAYAL", "2026-04-15", "sale", 500, 25000,
                            "2026-04-15T10:00:00+00:00")
            assert (await is_year_summary_stale(db, 2026)) is True
        finally:
            await _drop(client, db)
    _run(_t())


def test_is_stale_detects_deletion():
    async def _t():
        client, db = _fresh_db()
        try:
            await _seed_txn(db, "A", "2026-04-10", "sale", 1000, 50000,
                            "2026-04-10T10:00:00+00:00")
            await _seed_txn(db, "B", "2026-04-11", "sale", 2000, 80000,
                            "2026-04-11T10:00:00+00:00")
            await recompute_monthly_summaries(db, 2026)
            assert (await is_year_summary_stale(db, 2026)) is False
            await db.transactions.delete_one({"item_name": "B"})
            assert (await is_year_summary_stale(db, 2026)) is True
        finally:
            await _drop(client, db)
    _run(_t())


def test_ensure_year_summary_fresh_noop_when_clean():
    async def _t():
        client, db = _fresh_db()
        try:
            await _seed_txn(db, "A", "2026-04-10", "sale", 1000, 50000,
                            "2026-04-10T10:00:00+00:00")
            await recompute_monthly_summaries(db, 2026)
            res = await ensure_year_summary_fresh(db, 2026)
            assert res["recomputed"] is False
            assert res["last_computed_at"] is not None
        finally:
            await _drop(client, db)
    _run(_t())


def test_ensure_year_summary_fresh_recomputes_when_stale():
    async def _t():
        client, db = _fresh_db()
        try:
            await _seed_txn(db, "A", "2026-04-10", "sale", 1000, 50000,
                            "2026-04-10T10:00:00+00:00")
            await recompute_monthly_summaries(db, 2026)
            # New txn → stale → must recompute
            await _seed_txn(db, "B", "2026-04-15", "sale", 500, 25000,
                            "2026-04-15T10:00:00+00:00")
            res = await ensure_year_summary_fresh(db, 2026)
            assert res["recomputed"] is True
            assert res["txn_count"] == 2
        finally:
            await _drop(client, db)
    _run(_t())


def test_ensure_year_summary_fresh_no_transactions():
    """Year with zero transactions: should not crash and reports recomputed."""
    async def _t():
        client, db = _fresh_db()
        try:
            res = await ensure_year_summary_fresh(db, 2099)
            assert "recomputed" in res
            # No transactions → meta will be written with count=0
            meta = await get_year_meta(db, 2099)
            if meta:
                assert meta["txn_count"] == 0
        finally:
            await _drop(client, db)
    _run(_t())
