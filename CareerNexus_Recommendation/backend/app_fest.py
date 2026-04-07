# app_fest.py — CareerNexus search + recommendations (universities & jobs)
from __future__ import annotations
import sys, asyncio
from pathlib import Path
from dotenv import load_dotenv
# --- ADD THESE IMPORTS ---
import os, httpx
from fastapi import HTTPException
import os
from dotenv import load_dotenv
load_dotenv()
from services.job_aggregator import aggregate_jobs
import asyncio
from fastapi import APIRouter, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

bearer_scheme = HTTPBearer()

# 🧠 Windows event-loop fix
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# ✅ Explicit .env load (only once) — with override=True
env_path = Path(__file__).parent / ".env"
print("🔍 Loading .env from:", env_path)
load_dotenv(dotenv_path=env_path, override=True)

# ────────────────────────────────
# Standard library + third-party imports
# ────────────────────────────────
from typing import List, Optional
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import re
from datetime import datetime
from fastapi import APIRouter
from services.job_aggregator import fetch_serpapi_google_jobs  # keep this exact name


# ────────────────────────────────
# Internal imports
# ────────────────────────────────
from recommend.rank_jobs import rank_jobs         # your ranking logic
from services.job_aggregator import aggregate_jobs  # job API aggregation

def deduplicate_jobs(jobs):
    seen = set()
    unique = []

    for job in jobs:
        # best unique identifier
        key = job.get("apply_url")

        # fallback if apply_url missing
        if not key:
            key = f"{job.get('title')}|{job.get('company')}|{job.get('location')}"

        if key not in seen:
            seen.add(key)
            unique.append(job)

    return unique


# Model for the new endpoint body
class JobRequest(BaseModel):
    skills: list[str] = Field(default_factory=list)
    work_mode: str = "any"            # onsite|remote|hybrid|any
    job_type: str = "any"             # full_time|part_time|internship|contract|freelance|any
    preferred_locations: list[str] = Field(default_factory=list)
    salary_min: int | None = None
    experience_months: int = 0
    city: str | None = "Pakistan"
    limit: int = 20
    query: str | None = None          # optional free text e.g. "react developer"

# ---------------------------------------------------------------------------
# App & CORS
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CareerNexus Recommendation API",
    version="1.0.0",
    description="FEST/FULL search + CSV recommender + TF-IDF jobs/universities",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================
# Uni-Rec PROXY (forward to :8001)
# ===========================
UNI_REC_BASE = os.getenv("UNI_REC_BASE", "http://127.0.0.1:8001")

@app.get("/unirec/suggest")
def proxy_unirec_suggest(
    field: str = "", city: str = "", level: str = "",
    page: int = 1, page_size: int = 10, universities_limit: int = 6,
    max_fee: float | None = None
):
    params = {
        "field": field, "city": city, "level": level,
        "page": page, "page_size": page_size,
        "universities_limit": universities_limit
    }
    if max_fee is not None:
        params["max_fee"] = max_fee

    try:
        r = httpx.get(f"{UNI_REC_BASE}/v1/suggest/programs", params=params, timeout=20.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"uni-rec suggest failed: {e}")

@app.post("/unirec/recommend")
def proxy_unirec_recommend(payload: dict):
    try:
        r = httpx.post(f"{UNI_REC_BASE}/v1/recommend", json=payload, timeout=30.0)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"uni-rec recommend failed: {e}")

# ---------------------------------------------------------------------------
# Simple SerpAPI debug endpoint (direct on app)
# ---------------------------------------------------------------------------
# ---- DEBUG ROUTES ----
debug = APIRouter()

@debug.get("/debug/serpapi")
async def debug_serpapi(q: str = "developer", city: str = "Pakistan"):
    """Quick check to see what SerpAPI returns."""
    items = await fetch_serpapi_google_jobs(q, city)
    return {"count": len(items), "first": (items[0] if items else None)}

app.include_router(debug)
# ---- END DEBUG ROUTES ----


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug/keys")
def debug_keys():
    import os
    return {
        "ADZUNA_APP_ID": bool(os.getenv("ADZUNA_APP_ID")),
        "ADZUNA_APP_KEY": bool(os.getenv("ADZUNA_APP_KEY")),
        "SERPAPI_KEY": bool(os.getenv("SERPAPI_KEY")),
        "JOOBLE_API_KEY": bool(os.getenv("JOOBLE_API_KEY")),
        "JSEARCH_API_KEY": bool(os.getenv("JSEARCH_API_KEY")),
    }


# ---------------------------------------------------------------------------
# TF-IDF Recommendations via recommendation.py (Jobs + Universities)
# ---------------------------------------------------------------------------
# Your recommendation.py is expected to define RecommendEngine with:
# - recommend_jobs(skills: List[str], top_k: int) -> List[dict]
# - recommend_universities(skills: List[str], top_k: int) -> List[dict]
# using data/jobs.json and data/universities.json.
try:
    from recommendation import RecommendEngine
    _engine = RecommendEngine()
except Exception as e:
    _engine = None
    print(f"⚠️ TF-IDF engine not available: {e}")

class JobRecRequest(BaseModel):
    skills: List[str]
    top_k: int = 10

@app.post("/recommend/jobs", summary="Recommend jobs by skills (TF-IDF JSON)")
def recommend_jobs(req: JobRecRequest):
    if _engine is None:
        raise HTTPException(503, "Recommendation engine not initialized.")
    if not req.skills:
        return []
    return _engine.recommend_jobs(req.skills, req.top_k)

# ------------------------------
# NEW: Live Job Recommendation Endpoint (Jooble + JSearch)
# ------------------------------
@app.post("/recommend/jobs_live", summary="Live job recommendations with filters")
async def recommend_jobs_live(req: JobRequest):
    query = req.query or (" ".join(req.skills) if req.skills else "software developer")
    location = req.city or "Pakistan"

    raw_jobs = await aggregate_jobs(query, location)

    user = {
        "skills": req.skills,
        "experience_months": req.experience_months,
        "prefs": {
            "work_mode": req.work_mode,
            "job_type": req.job_type,
            "preferred_locations": req.preferred_locations or ([req.city] if req.city else []),
            "salary_min": req.salary_min
        }
    }

    ranked = rank_jobs(user, raw_jobs, limit=req.limit)
    return {"intent": "job_recommendation", "items": ranked}

from fastapi import APIRouter, Query
router = APIRouter()

@router.get("/jobs/search")
async def jobs_search(
    q: str = Query("", description="keywords, e.g., 'react developer'"),
    city: str = Query("Pakistan", description="city or country, e.g., 'Karachi'"),
):
    """
    Aggregate live jobs from JSearch, SerpAPI (Google Jobs), Adzuna.
    Make sure your .env has the required keys.
    """
    items = await aggregate_jobs(q, city)
    # Optional: sort or truncate here if you want
    return {"query": q, "location": city, "count": len(items), "items": items}

# Mount router (if you don’t already have one)
app.include_router(router, prefix="/v1")


from fastapi import HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
import os
import httpx

PROFILE_BASE = os.getenv("PROFILE_BASE", "http://127.0.0.1:8000")

@app.get("/recommend/jobs_from_profile", summary="Career-based real-time job recommendations (careers only)")
async def recommend_jobs_from_profile(
    city: str = "Pakistan",
    top_careers: int = 3,
    limit: int = 0,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    # ✅ Bearer token received from Swagger
    authorization = f"{creds.scheme} {creds.credentials}"

    # 1) Fetch profile + recommended_careers from Resume/Profile service (8000)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                f"{PROFILE_BASE}/profile/full/me",
                headers={"Authorization": authorization},
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch profile from {PROFILE_BASE}: {e}")

    # 2) Extract careers (primary driver)
    careers = data.get("recommended_careers") or []
    if not careers:
        raise HTTPException(status_code=400, detail="No recommended careers found for this user.")

    careers = careers[: max(1, min(top_careers, 5))]

    # (Optional) keep resume skills just to show user, but NOT used for job search
    resume = (data.get("profile") or {}).get("resume") or {}
    skills = resume.get("skills") or []

    # 3) For each career, fetch live jobs using CAREER ONLY
    output = []
    for career in careers:
        # ✅ Career-based query ONLY (teacher requirement)
        query = f"{career} jobs"

        raw_jobs = await aggregate_jobs(query, city)
        raw_jobs = deduplicate_jobs(raw_jobs)


        # ✅ No skills ranking, just take top N
        items = raw_jobs if (limit is None or int(limit) <= 0) else raw_jobs[:int(limit)]

        output.append({
            "career": career,
            "query_used": query,
            "count": len(items),
            "items": items
        })

    return {
        "intent": "career_based_job_recommendation",
        "location": city,
        "careers_used": careers,
        "skills_extracted": skills,  # just informational
        "results": output
    }

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import httpx
import os

PROFILE_BASE = os.getenv("PROFILE_BASE", "http://127.0.0.1:8000")

@app.get(
    "/recommend/jobs_from_resume",
    summary="Resume-based real-time job recommendations (skills driven)"
)
async def recommend_jobs_from_resume(
    city: str = "Pakistan",
    limit: int = 0,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    # Authorization header (same pattern as psychometric & profile)
    authorization = f"{creds.scheme} {creds.credentials}"

    # 1) Fetch full profile using token → email linkage
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                f"{PROFILE_BASE}/profile/full/me",
                headers={"Authorization": authorization},
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch profile from {PROFILE_BASE}: {e}",
        )

    # 2) Extract resume skills
    resume = (data.get("profile") or {}).get("resume") or {}
    skills = resume.get("skills") or []

    if not skills:
        raise HTTPException(
            status_code=400,
            detail="No resume skills found. Please update skills in profile first.",
        )

    # 3) Build job query purely from resume skills
    top_skills = skills[:8]
    query = " ".join(top_skills) + " jobs"

    # 4) Fetch jobs from existing aggregators
    raw_jobs = await aggregate_jobs(query, city)
    raw_jobs = deduplicate_jobs(raw_jobs)

    # 5) Limit results
    jobs = raw_jobs if (limit is None or int(limit) <= 0) else raw_jobs[:int(limit)]

    return {
        "intent": "resume_based_job_recommendation",
        "location": city,
        "query_used": query,
        "skills_used": top_skills,
        "count": len(jobs),
        "items": jobs,
    }
