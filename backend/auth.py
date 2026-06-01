from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
import secrets
from datetime import datetime, timezone, timedelta
from typing import List
import jwt
import os
from database import db

security = HTTPBearer()

# JWT signing key. Primary source: JWT_SECRET_KEY env var (set in .env and carried to deploy).
# The key MUST be STABLE across worker processes and restarts — otherwise a token issued by
# one worker fails validation on another, so the user logs in but is immediately rejected on
# the next request ("can't log in" in production). `ensure_secret_key()` (called on startup)
# resolves a stable key even when the env var is missing by persisting one in the DB so every
# worker shares the same secret. This replaces the previous per-process random fallback.
SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 18


async def ensure_secret_key(db_handle) -> str:
    """Resolve a STABLE JWT secret shared across all workers/restarts.

    Resolution order:
      1. JWT_SECRET_KEY env var (preferred, present in .env)
      2. key persisted in db.app_config (shared by all workers)
      3. generate a new key once and persist it
    """
    global SECRET_KEY
    if SECRET_KEY:
        return SECRET_KEY
    doc = await db_handle.app_config.find_one({"_id": "jwt_secret"})
    if doc and doc.get("value"):
        SECRET_KEY = doc["value"]
    else:
        SECRET_KEY = secrets.token_hex(32)
        await db_handle.app_config.update_one(
            {"_id": "jwt_secret"},
            {"$set": {"value": SECRET_KEY}},
            upsert=True,
        )
    return SECRET_KEY


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expire_hours: int = None) -> str:
    to_encode = data.copy()
    hours = expire_hours or ACCESS_TOKEN_EXPIRE_HOURS
    expire = datetime.now(timezone.utc) + timedelta(hours=hours)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return current user"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        user = await db.users.find_one({"username": username}, {"_id": 0, "password_hash": 0})
        if user is None or not user.get('is_active'):
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired - please login again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
