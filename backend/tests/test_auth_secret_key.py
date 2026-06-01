"""Auth hardening tests: stable JWT secret across workers + idempotent admin seed.

Reproduces the production login failure scenario where JWT_SECRET_KEY is missing in the
environment. Before the fix, each worker process generated its OWN random key, so a token
signed by worker A was rejected by worker B (HTTP 401 right after login). After the fix,
ensure_secret_key() persists a single key in db.app_config that all workers share.
"""
import asyncio
import os
import sys
import uuid

import jwt
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import auth  # noqa: E402

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_BASE = os.environ.get('DB_NAME', 'test_db')


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _client_and_name():
    client = AsyncIOMotorClient(MONGO_URL)
    return client, f"{DB_BASE}_authtest_{uuid.uuid4().hex[:8]}"


def test_stable_key_shared_across_workers_when_env_missing():
    """Two fresh 'workers' (env var missing) must resolve the SAME persisted key, and a
    token signed by one must validate under the other's key."""
    client, name = _client_and_name()
    saved = auth.SECRET_KEY

    async def scenario():
        db = client[name]
        try:
            # Worker A: no key in memory, none in DB -> generate + persist
            auth.SECRET_KEY = None
            key_a = await auth.ensure_secret_key(db)
            token = auth.create_access_token({"sub": "admin", "role": "admin"})
            # Worker B: fresh process (in-memory key None) -> must read SAME key from DB
            auth.SECRET_KEY = None
            key_b = await auth.ensure_secret_key(db)
            return key_a, key_b, token
        finally:
            await client.drop_database(name)

    try:
        key_a, key_b, token = _run(scenario())
        assert key_a == key_b, "All workers must share one persisted secret"
        decoded = jwt.decode(token, key_b, algorithms=["HS256"])
        assert decoded["sub"] == "admin"
    finally:
        auth.SECRET_KEY = saved
        client.close()


def test_env_var_takes_precedence_and_is_not_persisted():
    client, name = _client_and_name()
    saved = auth.SECRET_KEY

    async def scenario():
        db = client[name]
        try:
            auth.SECRET_KEY = "env-secret-value-1234567890"
            key = await auth.ensure_secret_key(db)
            doc = await db.app_config.find_one({"_id": "jwt_secret"})
            return key, doc
        finally:
            await client.drop_database(name)

    try:
        key, doc = _run(scenario())
        assert key == "env-secret-value-1234567890"
        assert doc is None, "Must not persist a key when env var is present"
    finally:
        auth.SECRET_KEY = saved
        client.close()


def test_seed_admin_idempotent():
    """seed_admin must create exactly one active admin and never duplicate it."""
    client, name = _client_and_name()

    async def scenario():
        import server
        db = client[name]
        orig_db = server.db
        server.db = db
        try:
            await server.seed_admin()
            await server.seed_admin()  # second run must be a no-op
            count = await db.users.count_documents({"username": "admin"})
            admin = await db.users.find_one({"username": "admin"})
            return count, admin
        finally:
            server.db = orig_db
            await client.drop_database(name)

    try:
        count, admin = _run(scenario())
        assert count == 1
        assert admin.get("is_active", True) is True
        assert admin.get("role") == "admin"
    finally:
        client.close()
