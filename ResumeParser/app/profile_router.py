# app/profile_router.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from pymongo import MongoClient

# ✅ Postgres session + read-only models (you created these)
from app.db_pg import get_pg
from app.models_pg import User, PersonalityResult
from .recommend import (
    fetch_job_recommendations_from_profile,
    fetch_university_recommendations_from_profile,
)

router = APIRouter(prefix="/profile", tags=["Unified Profile"])

# ---------- Mongo (same cluster your resume parser uses) ----------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "careernexus")
_mongo = MongoClient(MONGO_URI)
_mdb = _mongo[MONGO_DB]          # expects a 'resumes' collection


# ---------- helpers ----------
def _serialize_mongo(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    d = dict(doc)
    d.pop("_id", None)  # hide ObjectId
    # normalize datetimes if present
    for k in ("uploaded_at", "created_at"):
        v = d.get(k)
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


# ========== By email ==========
@router.get("/by-email/{email}")
def get_profile_by_email(email: str, db: Session = Depends(get_pg)):
    """
    Unified profile joined by email:
      - Postgres: users, personality_results (latest)
      - MongoDB : resumes (by email)
    """
    email_l = email.strip().lower()

    # 1) user (Postgres)
    user = db.execute(select(User).where(User.email == email_l)).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found in Postgres")

    # 2) latest psychometric (prefer FK user_id; fallback to legacy user_identifier=email)
    pr = db.execute(
        select(PersonalityResult)
        .where(
            (PersonalityResult.user_id == user.id)
            | (PersonalityResult.user_identifier == email_l)
        )
        .order_by(PersonalityResult.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    psychometric = None
    if pr:
        psychometric = {
            "scores": pr.scores,
            "dominant": pr.dominant,
            "summary": pr.summary,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
        }

    # 3) resume (Mongo) — by email (works even if you didn’t store user_id yet)
    resume = _mdb.resumes.find_one({"email": email_l}, {"_id": 0})
    resume = _serialize_mongo(resume)

    return {
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
        "resume": resume,
        "psychometric_result": psychometric,
    }


# ========== By user_id (UUID) ==========
@router.get("/{user_id}")
def get_profile_by_user_id(user_id: str, db: Session = Depends(get_pg)):
    """
    Unified profile joined by user_id:
      - Postgres: users(id), personality_results(user_id)
      - MongoDB : resumes(user_id) if present, else fallback to email
    """
    # 1) user (Postgres)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found in Postgres")

    # 2) latest psychometric (strict by user_id)
    pr = db.execute(
        select(PersonalityResult)
        .where(PersonalityResult.user_id == user.id)
        .order_by(PersonalityResult.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    psychometric = None
    if pr:
        psychometric = {
            "scores": pr.scores,
            "dominant": pr.dominant,
            "summary": pr.summary,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
        }

    # 3) resume (Mongo): first try user_id (if you stored it), else fallback to email
    resume = _mdb.resumes.find_one({"user_id": str(user.id)}, {"_id": 0})
    if not resume and user.email:
        resume = _mdb.resumes.find_one({"email": user.email.lower()}, {"_id": 0})
    resume = _serialize_mongo(resume)

    return {
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
        "resume": resume,
        "psychometric_result": psychometric,
    }

# ========== Unified profile + external recommendations (Jobs + Universities) ==========

def _build_profile_payload_for_recs(
    user: User,
    resume: Optional[Dict[str, Any]],
    psychometric: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a compact profile dict that job/uni microservices can understand.
    You can adjust the mapping as needed.
    """
    resume = resume or {}

    # Try to pull reasonable defaults from resume data
    skills = resume.get("skills") or []
    degree_program = (
        resume.get("degree_program")
        or resume.get("program")
        or resume.get("education_program")
        or ""
    )
    degree_level = resume.get("degree_level") or resume.get("level") or "bs"
    location = resume.get("location") or resume.get("city") or ""
    target_title = (
        resume.get("target_title")
        or resume.get("current_title")
        or resume.get("headline")
        or ""
    )

    return {
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
        "resume": resume,
        "psychometric_result": psychometric or {},
        # fields that job/uni services use:
        "skills": skills,
        "degree_program": degree_program,
        "degree_level": degree_level,
        "target_program": degree_program,
        "target_title": target_title,
        "location": location,
    }


@router.get("/with-recs/by-email/{email}")
async def get_profile_with_recs_by_email(
    email: str,
    db: Session = Depends(get_pg),
):
    """
    Full unified profile + job & university recommendations, joined by email.
    """
    email_l = email.strip().lower()

    # --- same logic as get_profile_by_email() ---
    user = db.execute(select(User).where(User.email == email_l)).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found in Postgres")

    pr = db.execute(
        select(PersonalityResult)
        .where(
            (PersonalityResult.user_id == user.id)
            | (PersonalityResult.user_identifier == email_l)
        )
        .order_by(PersonalityResult.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    psychometric = None
    if pr:
        psychometric = {
            "scores": pr.scores,
            "dominant": pr.dominant,
            "summary": pr.summary,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
        }

    resume = _mdb.resumes.find_one({"email": email_l}, {"_id": 0})
    resume = _serialize_mongo(resume)

    # --- build payload for job/uni services ---
    profile_payload = _build_profile_payload_for_recs(user, resume, psychometric)

    # --- call external microservices ---
    jobs = await fetch_job_recommendations_from_profile(profile_payload, limit=10)
    universities = await fetch_university_recommendations_from_profile(
        profile_payload, limit=10
    )

    return {
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
        "resume": resume,
        "psychometric_result": psychometric,
        "job_recommendations": jobs,
        "university_recommendations": universities,
    }


@router.get("/with-recs/{user_id}")
async def get_profile_with_recs_by_user_id(
    user_id: str,
    db: Session = Depends(get_pg),
):
    """
    Full unified profile + job & university recommendations, joined by user_id.
    """
    # --- same base as get_profile_by_user_id() ---
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found in Postgres")

    pr = db.execute(
        select(PersonalityResult)
        .where(PersonalityResult.user_id == user.id)
        .order_by(PersonalityResult.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    psychometric = None
    if pr:
        psychometric = {
            "scores": pr.scores,
            "dominant": pr.dominant,
            "summary": pr.summary,
            "created_at": pr.created_at.isoformat() if pr.created_at else None,
        }

    resume = _mdb.resumes.find_one({"user_id": str(user.id)}, {"_id": 0})
    if not resume and user.email:
        resume = _mdb.resumes.find_one({"email": user.email.lower()}, {"_id": 0})
    resume = _serialize_mongo(resume)

    # build payload and call services
    profile_payload = _build_profile_payload_for_recs(user, resume, psychometric)

    jobs = await fetch_job_recommendations_from_profile(profile_payload, limit=10)
    universities = await fetch_university_recommendations_from_profile(
        profile_payload, limit=10
    )

    return {
        "user": {"id": str(user.id), "email": user.email, "name": user.name},
        "resume": resume,
        "psychometric_result": psychometric,
        "job_recommendations": jobs,
        "university_recommendations": universities,
    }
