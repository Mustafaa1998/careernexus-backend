# app/routes/resume_proxy.py
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.external_service import get_profile_full_me

router = APIRouter(prefix="/resume", tags=["Resume"])
security = HTTPBearer()


@router.get("/me")
async def resume_me(creds: HTTPAuthorizationCredentials = Depends(security)):
    profile = await get_profile_full_me(creds.credentials)

    return {
        "email": profile.get("email"),
        "resume": profile.get("profile", {}).get("resume"),
        "recommended_careers": profile.get("recommended_careers"),
        "psychometric_result": profile.get("psychometric_result"),
    }
