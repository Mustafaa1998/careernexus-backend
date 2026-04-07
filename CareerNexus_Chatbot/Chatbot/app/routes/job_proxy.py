# app/routes/job_proxy.py
from fastapi import APIRouter, Depends, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.external_service import (
    recommend_jobs_from_profile,
    recommend_jobs_from_resume,
    recommend_jobs_live,
)

router = APIRouter(prefix="/jobs", tags=["Job"])
security = HTTPBearer()


@router.get("/from-profile")
async def jobs_from_profile(
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    return await recommend_jobs_from_profile(creds.credentials)


@router.get("/from-resume")
async def jobs_from_resume(
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    return await recommend_jobs_from_resume(creds.credentials)


@router.post("/recommend_live")
async def jobs_live(payload: dict = Body(...)):
    return await recommend_jobs_live(payload)
