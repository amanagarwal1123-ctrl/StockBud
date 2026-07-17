"""In-process memory regression check for the OOM streaming fix.

Runs get_current_inventory, get_book_closing_stock_as_of_date('2026-07-17'),
and monthly_summary_service._compute_year(db, 2025), measures peak RSS via
resource.getrusage.

Expected per bug report:
  peak RSS < 350 MB (previously ~950MB)
  book closing 2026-07-17: 431 items, net sum 305.684 kg
  _compute_year(db, 2025): 19794 docs written
"""
import os
import sys
import asyncio
import resource

sys.path.insert(0, "/app/backend")
os.chdir("/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    from services import stock_service
    from services import monthly_summary_service

    # Bind service globals to db if they use module-level db
    if hasattr(stock_service, "db") and stock_service.db is None:
        stock_service.db = db

    # 1) current inventory
    inv = await stock_service.get_current_inventory()
    if isinstance(inv, dict):
        totals = {k: inv.get(k) for k in ("total_net_wt", "total_gr_wt", "total_items")}
        neg_len = len(inv.get("negative_items", []) or [])
    else:
        totals = None
        neg_len = None
    peak1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    print(f"[step1] get_current_inventory totals={totals} negatives_len={neg_len} peak_rss_mb={peak1:.1f}")

    # 2) book closing as of 2026-07-17
    book = await stock_service.get_book_closing_stock_as_of_date("2026-07-17")
    # book is likely dict keyed by item -> weights, or (dict, meta)
    if isinstance(book, tuple):
        book_map = book[0]
    else:
        book_map = book
    if isinstance(book_map, dict):
        n_items = len(book_map)
        net_sum = 0.0
        for v in book_map.values():
            if isinstance(v, dict):
                net_sum += float(v.get("net_wt", v.get("net", 0.0)) or 0.0)
            elif isinstance(v, (int, float)):
                net_sum += float(v)
        print(f"[step2] book_closing 2026-07-17 items={n_items} net_sum_g={net_sum:.3f} net_sum_kg={net_sum/1000.0:.3f}")
    else:
        print(f"[step2] book_closing type={type(book_map)} val={str(book_map)[:200]}")
    peak2 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    print(f"[step2] peak_rss_mb={peak2:.1f}")

    # 3) _compute_year(db, 2025)
    result = await monthly_summary_service._compute_year(db, 2025)
    print(f"[step3] _compute_year(db,2025) result={result}")
    peak3 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    print(f"[step3] peak_rss_mb={peak3:.1f}")

    print(f"\nFINAL_PEAK_RSS_MB={peak3:.1f} (threshold: <350)")

asyncio.run(main())
