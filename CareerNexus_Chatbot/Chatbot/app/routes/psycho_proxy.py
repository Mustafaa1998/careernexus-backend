# app/routes/psycho_proxy.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.services.external_service import get_profile_full_me, list_psycho_results

router = APIRouter(prefix="/psycho", tags=["Psychometric"])
security = HTTPBearer(auto_error=False)


def _require_token(creds: HTTPAuthorizationCredentials | None) -> str:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token")
    return creds.credentials


def _pick_latest(all_rows: list[dict], email: str) -> dict | None:
    rows = [r for r in all_rows if (r.get("user_identifier") or "").lower() == (email or "").lower()]
    if not rows:
        return None

    def _dt(x: str):
        try:
            return datetime.fromisoformat(x.replace("Z", ""))
        except Exception:
            return datetime.min

    rows.sort(key=lambda r: _dt(r.get("created_at", "")), reverse=True)
    return rows[0]


@router.get("/me")
async def get_my_psychometric(creds: HTTPAuthorizationCredentials | None = Depends(security)):
    token = _require_token(creds)
    profile_bundle = await get_profile_full_me(token)

    email = profile_bundle.get("email") or (profile_bundle.get("profile") or {}).get("email") or ""
    psych = profile_bundle.get("psychometric_result")

    if psych:
        return {"email": email, "psychometric_result": psych}

    all_psy = await list_psycho_results()
    latest = _pick_latest(all_psy, email)
    return {"email": email, "psychometric_result": latest}
