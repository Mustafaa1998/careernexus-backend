# app/aptitude_router.py
from __future__ import annotations
import json, random
from pathlib import Path
from typing import Dict, Optional, List

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db_pg import get_pg
from app.deps import get_current_user  # you already have this
from app.models_pg import AptitudeResult, User

router = APIRouter(prefix="/aptitude", tags=["Aptitude"])

# ---------- Load dataset ----------
DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "aptitude_questions.json"

def _load_bank() -> List[dict]:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Dataset not found at {DATA_FILE}")

QUESTION_BANK: List[dict] = _load_bank()
ALLOWED_DOMAINS = {str(q.get("domain", "")).upper() for q in QUESTION_BANK if q.get("domain")}
ALLOWED_LEVELS = {"Intermediate", "Bachelors", "Masters"}  # extend if your data has more

# ---------- DTO ----------
class AptitudeAnswers(BaseModel):
    answers: Dict[str, int]             # {"CS_101": 1, "CS_205": 3} -> option index (0-based)
    domain: Optional[str] = None
    level: Optional[str] = None

# ---------- Endpoints ----------
@router.get("/domains")
def get_domains():
    return sorted(ALLOWED_DOMAINS)

@router.get("/questions")
def get_questions(
    domain: str = Query(..., description="Example: CS, IT, SE"),
    n: int = Query(6, ge=1, le=50),
    difficulty_min: int = Query(1, ge=1, le=5),
    difficulty_max: int = Query(5, ge=1, le=5),
    level: Optional[str] = Query(None, description="Intermediate | Bachelors | Masters"),
):
    d = domain.upper()
    if d not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {d}")

    pool = [
        q for q in QUESTION_BANK
        if str(q.get("domain", "")).upper() == d
        and difficulty_min <= int(q.get("difficulty", 1)) <= difficulty_max
        and (level is None or q.get("level") == level)
    ]
    if not pool:
        raise HTTPException(status_code=404, detail="No matching questions found.")

    random.shuffle(pool)
    selected = pool[:n]

    # 🔒 sanitize COPIES (do not pop from originals!)
    sanitized = []
    for q in selected:
        item = {k: v for k, v in q.items() if k != "answer_idx"}
        sanitized.append(item)

    return {"domain": d, "count": len(sanitized), "questions": sanitized}


@router.post("/score")
def calculate_score(payload: AptitudeAnswers):
    """Stateless scoring (no auth)."""
    return _score_impl(payload.answers, payload.domain, payload.level)

@router.post("/score/me")
def calculate_score_and_save(
    payload: AptitudeAnswers,
    db: Session = Depends(get_pg),
    current: User = Depends(get_current_user),
):
    """Score and persist attempt linked to JWT's user_id."""
    result = _score_impl(payload.answers, payload.domain, payload.level)
    row = AptitudeResult(
        user_id=current.id,
        domain=result["domain"],
        level=result["level"],
        total=result["total"],
        correct=result["correct"],
        percent=result["percent"],
        breakdown=result["breakdown"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    result["attempt_id"] = row.id
    return result

@router.get("/me/latest")
def my_latest_attempt(db: Session = Depends(get_pg), current: User = Depends(get_current_user)):
    row = (
        db.query(AptitudeResult)
        .filter(AptitudeResult.user_id == current.id)
        .order_by(AptitudeResult.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(404, "No attempts yet")
    return _row_to_dict(row)

@router.get("/me/history")
def my_attempt_history(limit: int = 10, db: Session = Depends(get_pg), current: User = Depends(get_current_user)):
    rows = (
        db.query(AptitudeResult)
        .filter(AptitudeResult.user_id == current.id)
        .order_by(AptitudeResult.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_row_to_dict(r) for r in rows]

# ---------- helpers ----------
def _row_to_dict(r: AptitudeResult) -> dict:
    return {
        "id": r.id,
        "domain": r.domain,
        "level": r.level,
        "total": r.total,
        "correct": r.correct,
        "percent": float(r.percent),
        "breakdown": r.breakdown,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

def _score_impl(answers: Dict[str, int] | None, domain: Optional[str], level: Optional[str]) -> dict:
    by_id = {str(q["id"]): q for q in QUESTION_BANK}
    if not answers:
        raise HTTPException(status_code=400, detail="No answers provided.")

    total = len(answers)
    correct = 0
    topic_stats: Dict[str, Dict[str, int]] = {}

    for qid, sel in answers.items():
        q = by_id.get(str(qid))
        if not q:
            continue

        # coerce to int & validate
        try:
            sel_idx = int(sel)
        except Exception:
            continue

        # If your dataset is 1-based, uncomment the next line:
        # sel_idx -= 1

        ans_idx = q.get("answer_idx")
        if ans_idx is None:
            # answer_idx got stripped earlier? With the fix above, this won't happen.
            continue

        topic = q.get("topic", "General")
        topic_stats.setdefault(topic, {"correct": 0, "total": 0})
        topic_stats[topic]["total"] += 1

        if sel_idx == int(ans_idx):
            correct += 1
            topic_stats[topic]["correct"] += 1

    percent = round((correct / total) * 100, 2) if total else 0.0
    breakdown = {
        topic: {
            "correct": data["correct"],
            "total": data["total"],
            "percent": round((data["correct"] / data["total"]) * 100, 2) if data["total"] else 0.0
        }
        for topic, data in topic_stats.items()
    }

    return {
        "domain": (domain or "").upper() or None,
        "level": level,
        "correct": correct,
        "total": total,
        "percent": percent,
        "breakdown": breakdown,
    }
