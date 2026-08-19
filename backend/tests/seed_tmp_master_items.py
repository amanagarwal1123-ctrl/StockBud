"""Temp seed/cleanup of TEST_ master items so the Item Groups dialog list can be
scroll-tested on mobile. Usage: python seed_tmp_master_items.py seed|clean
"""
import asyncio
import sys

from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient

env = dotenv_values("/app/backend/.env")


async def main(mode):
    cl = AsyncIOMotorClient(env["MONGO_URL"])
    db = cl[env["DB_NAME"]]
    if mode == "seed":
        docs = [{"item_name": f"TEST_QA_ITEM_{i:02d}", "stamp": "STAMP 1"} for i in range(40)]
        await db.master_items.insert_many(docs)
        print("seeded", len(docs))
    else:
        r = await db.master_items.delete_many({"item_name": {"$regex": "^TEST_QA_ITEM_"}})
        r2 = await db.item_groups.delete_many({"group_name": {"$regex": "^TEST_QA_ITEM_"}})
        print("cleaned master_items", r.deleted_count, "groups", r2.deleted_count)
    print("master_items count:", await db.master_items.count_documents({}))
    cl.close()


asyncio.run(main(sys.argv[1]))
