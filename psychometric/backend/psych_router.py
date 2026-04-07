# backend/psych_router.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db_pg import get_pg
from .deps import get_current_user
from .models_pg import PersonalityResult, User

router = APIRouter(prefix="/psych", tags=["Psychometrics"])

@router.post("/me")
def save_my_psych(
    payload: dict,
    db: Session = Depends(get_pg),
    current: User = Depends(get_current_user),
):
    pr = PersonalityResult(
        user_id=current.id,
        total_questions=payload.get("total_questions"),
        answered=payload.get("answered"),
        scores=payload.get("scores"),
        dominant=payload.get("dominant"),
        summary=payload.get("summary"),
    )
    db.add(pr)
    db.commit()
    db.refresh(pr)
    return {"id": pr.id}

@router.get("/me/latest")
def get_my_latest_psych(
    db: Session = Depends(get_pg),
    current: User = Depends(get_current_user),
):
    row = (
        db.query(PersonalityResult)
        .filter(PersonalityResult.user_id == current.id)
        .order_by(PersonalityResult.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No results yet")
    return {
        "id": row.id,
        "scores": row.scores,
        "dominant": row.dominant,
        "summary": row.summary,
        "created_at": row.created_at.isoformat(),
    }
