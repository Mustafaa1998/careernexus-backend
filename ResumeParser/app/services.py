# app/services.py
from __future__ import annotations
from typing import Optional, Dict, Any
from pymongo import MongoClient
import os

from app.models import UserProfile
from app.db import insert_user_profile, find_user_profile_by_id, find_user_profile_by_email

# --- Mongo connection (same as in app/api.py) ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "career_nexus")

_mongo = MongoClient(MONGO_URI)
_db = _mongo[MONGO_DB]
profiles = _db["user_profiles"]   # ✅ main collection for unified profiles


# ===========================================================
#  ✅ NEW: Save and fetch by user_id (modern, auth-linked)
# ===========================================================

async def save_user_profile(profile: UserProfile, *, user_id: str) -> str:
    """
    Save or update a unified user profile in MongoDB using the logged-in user's UUID.
    Overwrites the existing document with the same user_id.
    """
    doc = profile.dict()
    doc["user_id"] = user_id
    profiles.replace_one({"user_id": user_id}, doc, upsert=True)
    return user_id


async def get_user_profile_by_user_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a user's profile document by their user_id (UUID).
    """
    doc = profiles.find_one({"user_id": user_id})
    if doc:
        doc.pop("_id", None)
    return doc


# ===========================================================
#  🧩 Legacy support: Email-based lookup (for backward use)
# ===========================================================

async def save_user_profile_legacy(profile: UserProfile) -> str:
    """
    Old-style save (email-based). Deprecated — use save_user_profile(user_id=...) instead.
    """
    # ✅ Pydantic v1/v2 safe
    try:
        doc = profile.model_dump(by_alias=True, exclude_none=True)  # v2
    except Exception:
        doc = profile.dict(by_alias=True, exclude_none=True)        # v1
    return await insert_user_profile(doc)


async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a profile by internal Mongo _id (legacy).
    """
    return await find_user_profile_by_id(user_id)


async def get_user_profile_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Legacy: Find profile by email.
    Still works for old data that hasn’t been migrated to user_id.
    """
    email = (email or "").strip().lower()
    return await find_user_profile_by_email(email)
