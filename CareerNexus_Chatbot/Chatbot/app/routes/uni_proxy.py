# app/routes/uni_proxy.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.external_service import recommend_universities

router = APIRouter(prefix="/uni", tags=["University"])


class UniRequest(BaseModel):
    # ✅ make them optional so chat/extractor doesn't crash gateway
    level: Optional[str] = ""
    program_name: Optional[str] = ""
    field: str = ""
    city: str = ""
    limit: int = 5

    # (keep these if you need them)
    province: str = ""
    type: str = ""
    ranking_tier: str = ""
    ranking_min: int = 0
    offers_fest: bool = True
    sort_by: str = "ranking"
    order: str = "asc"
    page: int = 1
    page_size: int = 30


@router.post("/recommend")
async def uni_recommend(payload: UniRequest):
    # ✅ normalize: if program_name missing, use field (and vice versa)
    data = payload.model_dump()
    if not data.get("program_name") and data.get("field"):
        data["program_name"] = data["field"]
    if not data.get("field") and data.get("program_name"):
        data["field"] = data["program_name"]

    try:
        return await recommend_universities(data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"University proxy failed: {str(e)}")
