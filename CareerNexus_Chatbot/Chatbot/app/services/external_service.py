# app/services/external_service.py
import httpx
from typing import Dict, Any, Optional

PROFILE_API = "http://127.0.0.1:8000"
JOB_API = "http://127.0.0.1:8001"
UNI_API = "http://127.0.0.1:8002"
PSYCHO_API = "http://127.0.0.1:8003"

TIMEOUT = 60.0


def _auth_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# 🔐 PROFILE (MASTER SOURCE)
async def get_profile_full_me(token: str):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(
            f"{PROFILE_API}/profile/full/me",
            headers=_auth_headers(token),
        )
        res.raise_for_status()
        return res.json()


# ---------- JOBS (FIXED ENDPOINTS) ----------
async def recommend_jobs_from_profile(token: str):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(
            f"{JOB_API}/recommend/jobs_from_profile",
            headers=_auth_headers(token),
        )
        res.raise_for_status()
        return res.json()


async def recommend_jobs_from_resume(token: str):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(
            f"{JOB_API}/recommend/jobs_from_resume",
            headers=_auth_headers(token),
        )
        res.raise_for_status()
        return res.json()


async def recommend_jobs_live(payload: dict):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.post(
            f"{JOB_API}/recommend/jobs_live",
            json=payload,
        )
        res.raise_for_status()
        return res.json()


# 🌐 UNI (NO AUTH) — ✅ normalize payload + safe errors
async def recommend_universities(payload: Dict[str, Any]):
    """
    Uni service expects (from your recommender):
      level, field, city, max_fee(optional), limit(optional), program_name(optional), page, page_size
    We normalize so chat payload variations won't break it.
    """
    mapped: Dict[str, Any] = {
        "level": (payload.get("level") or "").strip(),
        "field": (payload.get("field") or "").strip(),
        "program_name": (payload.get("program_name") or "").strip(),
        "city": (payload.get("city") or "").strip(),
        "max_fee": payload.get("max_fee", None),
        "limit": int(payload.get("limit") or 5),
        "page": int(payload.get("page") or 1),
        "page_size": int(payload.get("page_size") or 30),
    }

    # If one is missing but the other exists, fill it
    if not mapped["program_name"] and mapped["field"]:
        mapped["program_name"] = mapped["field"]
    if not mapped["field"] and mapped["program_name"]:
        mapped["field"] = mapped["program_name"]

    # If still nothing, return empty (avoid 422)
    if not mapped["field"] and not mapped["program_name"]:
        return {"intent": "university_need_more", "total": 0, "items": []}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            res = await client.post(
                f"{UNI_API}/v1/recommend",
                json=mapped,
            )
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            # Return structured error so chatbot can show it
            return {
                "error": f"UNI {e.response.status_code}: {e.response.text}",
                "items": [],
                "total": 0,
            }
        except Exception as e:
            return {"error": str(e), "items": [], "total": 0}


# 🌐 PSYCHO LIST (NO AUTH)
async def list_psycho_results():
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(f"{PSYCHO_API}/tests/results")
        res.raise_for_status()
        return res.json()


# 🔐 PSYCHO (JWT) — keep only if you really have this endpoint
async def get_psycho_results(token: str):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(
            f"{PSYCHO_API}/psycho/me/latest",
            headers=_auth_headers(token),
        )
        res.raise_for_status()
        return res.json()
