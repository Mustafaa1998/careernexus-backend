# app/profile_aggregator.py

from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()

# 🔌 Adjust these URLs to your real ones
PSYCH_BASE = "http://127.0.0.1:8003"   # psychometric backend
RESUME_BASE = "http://127.0.0.1:8000"  # resume parser backend


@router.get("/v1/profile/bootstrap")
async def bootstrap_profile(email: str):
    """
    Called by Job/Uni/Chatbot UI to get combined profile
    using email as the key.
    """
    async with httpx.AsyncClient(timeout=40.0) as client:
        # 1️⃣ Get psychometric result by email
        # change path to your actual psychometric “get result” endpoint
        psych_url = f"{PSYCH_BASE}/results/{email}"
        psych_res = await client.get(psych_url)
        psych_data = None

        if psych_res.status_code == 200:
            psych_data = psych_res.json()
        else:
            psych_data = {"error": f"psychometric service {psych_res.status_code}"}

        # 2️⃣ Get resume profile by email
        # change path to your actual resume “get profile” endpoint
        resume_url = f"{RESUME_BASE}/profile/{email}"
        resume_res = await client.get(resume_url)
        resume_data = None

        if resume_res.status_code == 200:
            resume_data = resume_res.json()
        else:
            resume_data = {"error": f"resume service {resume_res.status_code}"}

    # 3️⃣ Combined response
    return {
        "email": email,
        "from_resume": resume_data,
        "from_psychometric": psych_data,
    }
