import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv('.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

async def check():
    years = await db.historical_transactions.distinct('historical_year')
    print('Historical years:', sorted(years))
    
    for yr in sorted(years):
        sample = await db.historical_transactions.find(
            {'historical_year': yr},
            {'_id': 0, 'date': 1, 'type': 1, 'item_name': 1}
        ).limit(3).to_list(3)
        print(f'\nYear {yr} samples:')
        for s in sample:
            print(f'  date={s.get("date")}, type={s.get("type")}')
    
    # All month keys with their historical_year
    pipeline = [
        {"$addFields": {"month_key": {"$substr": ["$date", 0, 7]}}},
        {"$group": {"_id": {"mk": "$month_key", "hy": "$historical_year"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.hy": 1, "_id.mk": 1}}
    ]
    months = await db.historical_transactions.aggregate(pipeline).to_list(None)
    print('\nAll month_key -> historical_year mappings:')
    for m in months:
        print(f'  month_key={m["_id"]["mk"]}, historical_year={m["_id"]["hy"]}, count={m["count"]}')
    
    # Check specifically for 2026 dates
    sample_2026 = await db.historical_transactions.find(
        {"date": {"$regex": "^2026"}},
        {"_id": 0, "date": 1, "type": 1, "item_name": 1, "historical_year": 1}
    ).limit(10).to_list(10)
    print(f'\nSample docs with dates starting with 2026 ({len(sample_2026)} found):')
    for s in sample_2026:
        print(f'  date={s.get("date")}, hist_year={s.get("historical_year")}, type={s.get("type")}, item={s.get("item_name")}')

asyncio.run(check())
