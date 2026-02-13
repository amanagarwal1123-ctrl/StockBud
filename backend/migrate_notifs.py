import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv('.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

async def migrate():
    stamp_types = ['stamp_approval', 'stamp_verification', 'full_stock_match', 'stock_entry']
    r1 = await db.notifications.update_many(
        {"type": {"$in": stamp_types}, "category": {"$exists": False}},
        {"$set": {"category": "stamp"}}
    )
    print(f"Migrated {r1.modified_count} old stamp notifications → category='stamp'")

    r2 = await db.notifications.update_many(
        {"for_role": {"$exists": True}, "target_user": {"$exists": False}},
        [{"$set": {"target_user": "$for_role"}}]
    )
    print(f"Migrated {r2.modified_count} for_role → target_user")

    r3 = await db.notifications.update_many(
        {"created_at": {"$exists": True}, "timestamp": {"$exists": False}},
        [{"$set": {"timestamp": "$created_at"}}]
    )
    print(f"Migrated {r3.modified_count} created_at → timestamp")

    # Final counts
    for cat in ['stock', 'order', 'stamp', 'polythene', 'general']:
        if cat == 'general':
            c = await db.notifications.count_documents({"$or": [{"category": "general"}, {"category": {"$exists": False}}]})
        else:
            c = await db.notifications.count_documents({"category": cat})
        print(f"  {cat}: {c}")

asyncio.run(migrate())
