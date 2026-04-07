# app/recommend_router.py
from __future__ import annotations
from typing import Any, Dict
from urllib.parse import quote, unquote
import os
import httpx
from fastapi import APIRouter, HTTPException
from pymongo import MongoClient

from app.recommend import recommend_from_profile
from app.services import get_user_profile_by_email  # your existing async service

router = APIRouter(tags=["recommendations"])

# --- Mongo connection to pull the latest resume edits ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
_mongo = MongoClient(MONGO_URI)
_mdb = _mongo["career_nexus"]


def _merge_latest_resume(unified: Dict[str, Any]) -> Dict[str, Any]:
    """
    Overwrite unified['resume'] fields with the latest flat fields
    from Mongo 'resumes' doc (skills, education, experience, summary, certifications).
    """
    email = (unified.get("email") or "").lower()
    if not email:
        return unified

    doc = _mdb.resumes.find_one({"email": email})
    if not doc:
        return unified

    resume = unified.get("resume") or {}
    resume["skills"] = doc.get("skills", resume.get("skills", []))
    resume["education"] = doc.get("education", resume.get("education", []))
    resume["experience"] = doc.get("experience", resume.get("experience", ""))
    resume["summary"] = doc.get("summary", resume.get("summary", ""))
    resume["certifications"] = doc.get("certifications", resume.get("certifications", []))
    # NEW: include projects so it's editable & visible in with-recs
    resume["projects"] = doc.get("projects", resume.get("projects", []))
    unified["resume"] = resume
    return unified


async def _fetch_profile_resilient(email: str) -> Dict[str, Any] | None:
    """Try the service (case-insensitive), then fall back to the HTTP endpoint."""
    email_norm = (unquote(email) or "").strip()
    low = email_norm.lower()

    prof = await get_user_profile_by_email(low)
    if prof:
        return prof

    if low != email_norm:
        prof = await get_user_profile_by_email(email_norm)
        if prof:
            return prof

    # Fallback to your existing HTTP endpoint (works in Swagger)
    url = f"http://127.0.0.1:8000/profile/by-email/{quote(email_norm)}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    return None


# --- NEW: ensure psychometric_result is present by refetching unified if missing ---
async def _ensure_psychometric(profile: Dict[str, Any]) -> Dict[str, Any]:
    if profile.get("psychometric_result"):
        return profile  # already present

    email = (profile.get("email") or "").strip()
    if not email:
        return profile

    url = f"http://127.0.0.1:8000/profile/by-email/{quote(email)}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url)
        if r.status_code == 200:
            unified = r.json()
            if unified.get("psychometric_result"):
                profile["psychometric_result"] = unified["psychometric_result"]
    except Exception:
        pass

    return profile


@router.get("/recommendations/{email}")
async def get_career_recommendations(email: str) -> Dict[str, Any]:
    profile = await _fetch_profile_resilient(email)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return {"recommended_careers": recommend_from_profile(profile, top_k=3)}


@router.get("/profile/with-recs/by-email/{email}")
async def get_profile_with_recommendations(email: str) -> Dict[str, Any]:
    profile = await _fetch_profile_resilient(email)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    # Merge latest editable resume fields from Mongo
    profile = _merge_latest_resume(profile)
    # Ensure psychometric_result is present (backfill from unified if join missed it)
    profile = await _ensure_psychometric(profile)

    profile["recommended_careers"] = recommend_from_profile(profile, top_k=3)
    return profile
