import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv('.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

async def check():
    mappings = await db.item_mappings.find(
        {"transaction_name": {"$regex": "JB-70 KADA"}}, {"_id": 0}
    ).to_list(100)
    print(f"Mappings for JB-70 KADA*: {len(mappings)}")
    for m in mappings[:15]:
        print(f"  '{m['transaction_name']}' -> '{m['master_name']}'")

    masters = await db.master_items.find(
        {"item_name": {"$regex": "JB-70 KADA"}}, {"_id": 0, "item_name": 1}
    ).to_list(100)
    print(f"\nMaster items matching JB-70 KADA*: {len(masters)}")
    for m in masters:
        print(f"  '{m['item_name']}'")

    # Check groups for JB-70
    groups = await db.item_groups.find({}, {"_id": 0}).to_list(100)
    print(f"\nAll groups:")
    for g in groups:
        print(f"  {g['group_name']} -> {g['members']}")

asyncio.run(check())
