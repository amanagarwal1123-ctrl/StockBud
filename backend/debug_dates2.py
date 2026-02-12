import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv('.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

async def check():
    # Check raw date formats stored in the DB
    # Get a sample of dates to see what format they're stored as
    sample = await db.historical_transactions.find(
        {'historical_year': '2025'},
        {'_id': 0, 'date': 1}
    ).limit(30).to_list(30)
    
    dates = [s['date'] for s in sample if s.get('date')]
    print("Sample stored dates (first 30):")
    for d in dates:
        print(f"  '{d}'")
    
    # Check distinct month keys
    pipeline = [
        {"$match": {"historical_year": "2025"}},
        {"$addFields": {"month_key": {"$substr": ["$date", 0, 7]}}},
        {"$group": {"_id": "$month_key", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    months = await db.historical_transactions.aggregate(pipeline).to_list(None)
    print(f"\nMonth distribution for year 2025 ({sum(m['count'] for m in months)} total docs):")
    for m in months:
        print(f"  {m['_id']}: {m['count']} records")
    
    # Check if there are ANY dates beyond Feb 2026
    future = await db.historical_transactions.count_documents({
        "historical_year": "2025",
        "date": {"$gt": "2026-02-28"}
    })
    print(f"\nRecords with dates after Feb 2026: {future}")
    
    if future > 0:
        future_sample = await db.historical_transactions.find(
            {"historical_year": "2025", "date": {"$gt": "2026-02-28"}},
            {"_id": 0, "date": 1, "type": 1, "item_name": 1}
        ).limit(10).to_list(10)
        print("Sample future-dated records:")
        for s in future_sample:
            print(f"  date={s['date']}, type={s['type']}, item={s.get('item_name','')}")

asyncio.run(check())
