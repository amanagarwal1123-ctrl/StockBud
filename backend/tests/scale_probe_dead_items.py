"""Production-scale probe: seed 560k main + 220k historical synthetic docs in an
isolated scratch DB (with the same indexes production gets) and time the real
_compute_dead_items + _dead_coverage_cutoff + /stats-style queries."""
import asyncio
import os
import random
import resource
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import server  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

SCRATCH = 'dead_items_scale_probe'
N_MAIN, N_HIST = 560_000, 220_000
ITEMS = [f'ITEM-{i:04d}' for i in range(2000)]
PARTIES = [f'PARTY-{i:03d}' for i in range(400)]
TYPES = ['sale'] * 70 + ['purchase'] * 25 + ['sale_return'] * 3 + ['purchase_return'] * 2


def gen(n, d0, d1, seed):
    rng = random.Random(seed)
    span = (d1 - d0).days
    for _ in range(n):
        d = d0 + timedelta(days=rng.randrange(span))
        yield {'id': str(uuid.uuid4()), 'item_name': rng.choice(ITEMS),
               'type': rng.choice(TYPES), 'date': f'{d.isoformat()} 10:00:00',
               'net_wt': round(rng.uniform(50, 5000), 1),
               'refno': str(rng.randrange(1, 99999)), 'party_name': rng.choice(PARTIES)}


async def seed(tdb):
    if await tdb.transactions.estimated_document_count() >= N_MAIN:
        print('already seeded, skipping')
        return
    for c in ('transactions', 'historical_transactions', 'item_mappings', 'item_groups',
              'master_items', 'dead_item_removals'):
        await tdb[c].delete_many({})
    t0 = time.time()
    for coll, n, d0, d1, seed_v in (
            (tdb.transactions, N_MAIN, date(2024, 1, 1), date(2026, 7, 15), 1),
            (tdb.historical_transactions, N_HIST, date(2019, 1, 1), date(2023, 12, 31), 2)):
        batch = []
        for doc in gen(n, d0, d1, seed_v):
            batch.append(doc)
            if len(batch) == 20000:
                await coll.insert_many(batch, ordered=False)
                batch = []
        if batch:
            await coll.insert_many(batch, ordered=False)
    print(f'seeded {N_MAIN}+{N_HIST} docs in {time.time()-t0:.1f}s')
    t0 = time.time()
    await tdb.transactions.create_index('date')
    await tdb.transactions.create_index([('date', 1), ('type', 1)])
    await tdb.transactions.create_index('party_name')
    await tdb.transactions.create_index('item_name')
    await tdb.historical_transactions.create_index('date')
    await tdb.historical_transactions.create_index([('date', 1), ('type', 1)])
    print(f'indexes built in {time.time()-t0:.1f}s')


async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    tdb = client[SCRATCH]
    await seed(tdb)
    orig = server.db
    server.db = tdb
    try:
        t0 = time.time()
        cutoff = await server._dead_coverage_cutoff()
        print(f'coverage cutoff: {cutoff} in {time.time()-t0:.2f}s')

        t0 = time.time()
        data = await server._compute_dead_items('2026-07-15')
        dt = time.time() - t0
        items, review, _ = server._dead_split(data, {})
        print(f'_compute_dead_items: {dt:.1f}s | rows={len(data["rows"])} items={len(items)} review={len(review)}')

        t0 = time.time()
        total = await tdb.transactions.estimated_document_count()
        parties = await tdb.transactions.distinct('party_name')
        first = await tdb.transactions.find_one({'date': {'$gt': ''}}, {'_id': 0, 'date': 1}, sort=[('date', 1)])
        last = await tdb.transactions.find_one({'date': {'$gt': ''}}, {'_id': 0, 'date': 1}, sort=[('date', -1)])
        print(f'stats-style queries: {time.time()-t0:.2f}s | total={total} parties={len(parties)} range={first["date"][:10]}..{last["date"][:10]}')

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        print(f'peak RSS: {rss:.0f} MB')
    finally:
        server.db = orig
    client.close()

asyncio.run(main())
