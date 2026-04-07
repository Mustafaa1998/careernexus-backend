from __future__ import annotations
import os
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from bson import ObjectId

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "careernexus")

_client: Optional[AsyncIOMotorClient] = None

async def get_db():
    """Return database instance (singleton client)."""
    global _client
    if _client is None:
        if not MONGO_URI:
            raise RuntimeError("MONGO_URI is not set in environment/.env")
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client[MONGO_DB]

# ---------- CRUD ----------
async def insert_user_profile(doc: Dict[str, Any]) -> str:
    db = await get_db()
    res = await db.user_profiles.insert_one(doc)
    return str(res.inserted_id)

async def find_user_profile_by_id(id_str: str) -> Optional[Dict[str, Any]]:
    db = await get_db()
    try:
        oid = ObjectId(id_str)
    except Exception:
        return None
    doc = await db.user_profiles.find_one({"_id": oid})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

async def find_user_profile_by_email(email: str) -> Optional[Dict[str, Any]]:
    db = await get_db()
    doc = await db.user_profiles.find_one({"email": email})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc

async def ensure_indexes():
    db = await get_db()
    await db.user_profiles.create_index("email", unique=False)

# quick manual connectivity test
async def test_connection():
    db = await get_db()
    await ensure_indexes()
    await db.command("ping")
    print("✅ Connected successfully to MongoDB Atlas!")
