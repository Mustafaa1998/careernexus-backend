"""
CareerNexus Backend
FastAPI app exposing resume upload, tests (aptitude, Big Five, quick test, MBTI),
and simple recommendations. Personality questions are loaded from
backend/data/personality_questions.json (built by the prepare script).
"""

from __future__ import annotations

import os
import io
import json
import random
from pathlib import Path
from typing import List, Optional, Dict, Any

import joblib
import pandas as pd
import pdfplumber
import spacy
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.orm import Session

# 🔐 NEW: lightweight JWT dependency (kept inside this file)
import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from resume_parser import parse_resume

#from .resume_parser import parse_resume
from recommendation import RecommendEngine

# DB bits
from db import get_db
from models import PersonalityResult, User
from dotenv import load_dotenv
load_dotenv()

# ----------------------------------------------------------------------
# JWT helpers (kept inline to avoid touching other files)
# ----------------------------------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
_bearer = HTTPBearer(auto_error=True)

def _decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = _decode_token(creds.credentials)
        sub = payload.get("sub")
        if not sub:
            raise ValueError("missing sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # SQLAlchemy 2.x style
    user = db.get(User, sub)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# -----------------------------------------------------------------------------
# App & CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="CareerNexus API", version="0.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*",  # allow all (temporary for local testing)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Engines (loaded once)
# -----------------------------------------------------------------------------
nlp = spacy.load("en_core_web_sm")
recommender = RecommendEngine()

# -----------------------------------------------------------------------------
# Models / Schemas (Pydantic)
# -----------------------------------------------------------------------------
class ResumeData(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: List[str] = []
    education: List[str] = []
    experience: List[str] = []


class TestSubmission(BaseModel):
    """Full-bank personality answers: integers 1..5 in same order as served."""
    answers: List[int]


class Profile(BaseModel):
    skills: List[str]
    education: List[str] = []
    experience: List[str] = []
    aptitude_score: Optional[int] = None
    personality_type: Optional[str] = None


class MBTIPredictBody(BaseModel):
    """MBTI prediction body (numeric scale like -3..+3; length must match model)."""
    answers: List[float]


class QuickAnswer(BaseModel):
    questionId: int
    answer: int  # 1..5


class QuickSubmit(BaseModel):
    # Treat this as email for now (legacy); later your frontend can send user_id instead.
    user_identifier: Optional[str] = None
    answers: List[QuickAnswer]

# -----------------------------------------------------------------------------
# Data paths & helpers
# -----------------------------------------------------------------------------
DATA_FILE = Path(__file__).parent / "data" / "personality_questions.json"
MBTI_MODEL_PATH = Path(__file__).parent / "models" / "mbti.joblib"
MBTI_META_PATH = Path(__file__).parent / "models" / "mbti_meta.json"


def load_question_bank() -> Dict:
    if not DATA_FILE.exists():
        raise HTTPException(
            500, "personality_questions.json missing. Run the prepare script first."
        )
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_mbti_assets():
    if not MBTI_MODEL_PATH.exists() or not MBTI_META_PATH.exists():
        return None, None
    model = joblib.load(MBTI_MODEL_PATH)
    meta = json.loads(MBTI_META_PATH.read_text())
    return model, meta


# --- Quick test helpers (balanced random selection + MBTI approx) ---
def _bucket_questions_by_trait(bank: Dict[str, Any]) -> Dict[str, list]:
    buckets = {"O": [], "C": [], "E": [], "A": [], "N": []}
    for q in bank["questions"]:
        t = q.get("trait")
        if t in buckets:
            buckets[t].append(q)
    return buckets


def select_random_questions(n: int, seed: Optional[int] = None) -> Dict[str, Any]:
    bank = load_question_bank()
    buckets = _bucket_questions_by_trait(bank)
    if seed is not None:
        random.seed(seed)

    traits = ["O", "C", "E", "A", "N"]
    for t in traits:
        random.shuffle(buckets[t])

    selected = []
    idx = {t: 0 for t in traits}
    while len(selected) < n:
        for t in traits:
            if len(selected) >= n:
                break
            if idx[t] < len(buckets[t]):
                q = buckets[t][idx[t]]
                selected.append(
                    {
                        "id": q["id"],
                        "trait": t,
                        "text": q["text"],
                        "reverse": q.get("reverse", False),
                    }
                )
                idx[t] += 1
        if all(idx[t] >= len(buckets[t]) for t in traits):
            break

    return {
        "count": len(selected),
        "likert": [{"id": o["id"], "label": o["label"], "score": o["score"]} for o in bank["likert"]],
        "questions": selected,
    }


def score_ocean_for_subset(answers: List[Dict[str, int]]) -> Dict[str, float]:
    bank = load_question_bank()
    q_index = {q["id"]: q for q in bank["questions"]}
    traits = ["O", "C", "E", "A", "N"]
    raw = {t: 0.0 for t in traits}
    cnt = {t: 0 for t in traits}

    for i, a in enumerate(answers):
        qid = a.get("questionId")
        ans = a.get("answer")
        if not isinstance(ans, int) or ans < 1 or ans > 5:
            raise HTTPException(422, f"answers[{i}].answer must be 1..5")
        q = q_index.get(qid)
        if not q:
            continue
        t = q.get("trait")
        if t not in raw:
            continue
        score = 6 - ans if q.get("reverse") else ans
        raw[t] += score
        cnt[t] += 1

    # normalize 0..100
    scores: Dict[str, float] = {}
    for t in traits:
        if cnt[t] == 0:
            scores[t] = 0.0
        else:
            min_raw = 1 * cnt[t]
            max_raw = 5 * cnt[t]
            val = (raw[t] - min_raw) / (max_raw - min_raw) * 100.0
            scores[t] = round(float(val), 2)
    return scores


def bigfive_to_mbti(scores: Dict[str, float]) -> str:
    E = scores.get("E", 50.0)
    O = scores.get("O", 50.0)
    A = scores.get("A", 50.0)
    C = scores.get("C", 50.0)

    IorE = "E" if E >= 50 else "I"
    SorN = "N" if O >= 50 else "S"
    TorF = "T" if A < 50 else "F"
    JorP = "J" if C >= 50 else "P"
    return f"{IorE}{SorN}{TorF}{JorP}"

# -----------------------------------------------------------------------------
# Persistence helper: resolve/create user, then save result with user_id
# -----------------------------------------------------------------------------
def save_psychometric(
    db: Session,
    email: Optional[str],
    scores: Dict[str, float],
    mbti: str,
    total_questions: int,
    answered: int,
    summary: str,
    dominant: str,
) -> PersonalityResult:
    """
    Resolves/creates user by email (if provided) and stores a PersonalityResult
    linked via user_id. Keeps user_identifier (legacy) for compatibility.
    """
    email_l = (email or "").strip().lower() or None

    user_obj = None
    if email_l:
        user_obj = db.execute(select(User).where(User.email == email_l)).scalar_one_or_none()
        if not user_obj:
            user_obj = User(email=email_l)
            db.add(user_obj)
            db.commit()
            db.refresh(user_obj)

    rec = PersonalityResult(
        user_id=(user_obj.id if user_obj else None),
        user_identifier=email_l,  # legacy column
        total_questions=total_questions,
        answered=answered,
        scores=scores,
        dominant=dominant,
        summary=summary,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

# -----------------------------------------------------------------------------
# NEW: JWT-protected psych routes (by user_id) — no email needed
# -----------------------------------------------------------------------------
@app.post("/psych/me")
def save_my_psych(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
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

@app.get("/psych/me/latest")
def get_my_latest_psych(
    db: Session = Depends(get_db),
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

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.post("/upload_resume", response_model=ResumeData)
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume (PDF/DOCX/other text) and extract structured fields."""
    contents = await file.read()
    text = ""
    if file.filename.lower().endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                text += t + "\n"
    else:
        text = contents.decode("utf-8", errors="ignore")

    parsed = parse_resume(text, nlp)
    return ResumeData(**parsed)


@app.post("/tests/aptitude")
async def aptitude_test(submission: TestSubmission):
    """Tiny demo aptitude test – assumes correct answers [1,2,3,4,5]."""
    correct = [1, 2, 3, 4, 5]
    take = submission.answers[: len(correct)]
    score = sum(1 for i, ans in enumerate(take) if ans == correct[i])
    return {"score": score, "total": len(correct)}


@app.get("/tests/personality/questions")
def get_personality_questions():
    """Serve full personality questions & Likert options (1..5)."""
    bank = load_question_bank()
    return {
        "count": len(bank["questions"]),
        "questions": [
            {
                "id": q["id"],
                "text": q["text"],
                "options": [{"id": o["id"], "label": o["label"]} for o in bank["likert"]],
            }
            for q in bank["questions"]
        ],
    }


@app.post("/tests/personality")
def personality_test(submission: TestSubmission):
    """
    Score Big-Five (OCEAN) on the full bank; normalize 0–100 per trait.
    Input: {"answers":[1..5, ...]} aligned to /tests/personality/questions.
    """
    bank = load_question_bank()
    questions = bank["questions"]
    if not questions:
        raise HTTPException(500, "No questions loaded.")

    if not submission.answers:
        raise HTTPException(422, "answers must be a non-empty list of integers (1..5).")

    n = min(len(submission.answers), len(questions))
    traits = ["O", "C", "E", "A", "N"]
    raw: Dict[str, float] = {t: 0.0 for t in traits}
    cnt: Dict[str, int] = {t: 0 for t in traits}

    for i in range(n):
        ans = submission.answers[i]
        if not isinstance(ans, int) or ans < 1 or ans > 5:
            raise HTTPException(422, f"answers[{i}] must be an integer 1..5.")
        q = questions[i]
        t = q.get("trait")
        if t not in raw:
            continue
        score = 6 - ans if q.get("reverse") else ans
        raw[t] += score
        cnt[t] += 1

    scores: Dict[str, float] = {}
    for t in traits:
        if cnt[t] == 0:
            scores[t] = 0.0
        else:
            min_raw = 1 * cnt[t]
            max_raw = 5 * cnt[t]
            val = (raw[t] - min_raw) / (max_raw - min_raw) * 100.0
            scores[t] = round(float(val), 2)

    pretty = {"O": "Openness", "C": "Conscientiousness", "E": "Extraversion", "A": "Agreeableness", "N": "Neuroticism"}
    pretty_scores = {pretty[k]: v for k, v in scores.items()}
    dominant = max(pretty_scores, key=pretty_scores.get)

    return {
        "scores": pretty_scores,
        "dominant": dominant,
        "answered": n,
        "total_questions": len(questions),
        "summary": f"Dominant trait: {dominant}.",
    }


# -------------------- QUICK TEST (10–15 random items) --------------------
@app.get("/tests/quick/questions")
def quick_questions(n: int = Query(30, ge=5, le=60), seed: Optional[int] = None):
    """Return ~balanced random set of n questions (Likert 1..5)."""
    return select_random_questions(n=n, seed=seed)


@app.post("/tests/quick/submit")
def quick_submit(body: QuickSubmit, db: Session = Depends(get_db)):
    """
    Submit answers to quick test, compute Big-Five + approx MBTI,
    and SAVE the result into PostgreSQL (linked to users if email provided).
    Body:
      {
        "user_identifier": "hamna@iqra.edu.pk",   # treated as email for now
        "answers":[{"questionId": 101, "answer": 4}, ...]
      }
    """
    if not body.answers:
        raise HTTPException(422, "answers must be a non-empty list.")

    # Compute OCEAN using just the answered subset
    ocean = score_ocean_for_subset([a.dict() for a in body.answers])

    # Pretty names
    pretty_map = {"O": "Openness", "C": "Conscientiousness", "E": "Extraversion", "A": "Agreeableness", "N": "Neuroticism"}
    pretty_scores = {pretty_map[k]: v for k, v in ocean.items()}
    dominant = max(pretty_scores, key=pretty_scores.get) if pretty_scores else "Unknown"

    mbti = bigfive_to_mbti(ocean)
    summary = f"Dominant trait: {dominant}. Approx MBTI: {mbti}"
    answered = len(body.answers)

    # For bookkeeping: total_questions reflects the whole bank size
    bank = load_question_bank()
    total_questions = len(bank["questions"])

    # Persist (now creates/links user → sets user_id on the result)
    rec = save_psychometric(
        db=db,
        email=body.user_identifier,           # treat as email for now
        scores=pretty_scores,
        mbti=mbti,
        total_questions=total_questions,
        answered=answered,
        summary=summary,
        dominant=dominant,
    )

    return {
        "scores": pretty_scores,
        "approx_mbti": mbti,
        "dominant": dominant,
        "answered": answered,
        "total_questions": total_questions,
        "summary": summary,
        "attempt_id": rec.id,
        "note": "Saved to database.",
    }


# -------------------- RECS & MBTI ML --------------------
@app.post("/recommend/universities")
async def recommend_universities(profile: Profile):
    """Recommend university programs based on skills and education."""
    recs = recommender.recommend_universities(profile.skills)
    return {"recommendations": recs}


@app.post("/recommend/jobs")
async def recommend_jobs(profile: Profile):
    """Recommend jobs based on skills and experience."""
    recs = recommender.recommend_jobs(profile.skills)
    return {"recommendations": recs}


@app.post("/tests/personality/predict")
def predict_mbti(body: MBTIPredictBody):
    """
    Predict MBTI type using the trained model.
    Body: {"answers":[ ... <length must equal meta['n_items']> ... ]}
    Values should match the scale used in training (e.g., -3..+3).
    """
    model, meta = load_mbti_assets()
    if model is None:
        raise HTTPException(500, "MBTI model not available. Train it first.")

    feats = meta["feature_names"]
    n = meta["n_items"]
    if len(body.answers) != n:
        raise HTTPException(422, f"Expected {n} answers (found {len(body.answers)}).")

    X = pd.DataFrame([body.answers], columns=feats)
    label = model.predict(X)[0]

    proba = None
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)[0]
        # For pipelines: clf is usually the final step
        clf = getattr(model, "named_steps", {}).get("clf", None)
        classes = list(getattr(clf, "classes_", [])) if clf is not None else []
        if classes:
            proba = {cls: float(p) for cls, p in zip(classes, probs)}

    return {
        "label": label,
        "probabilities": proba,
        "expected_items": n,
        "range_hint": meta.get("input_range_hint", [-3, 3]),
    }


@app.get("/tests/results")
def list_results(db: Session = Depends(get_db)):
    rows = db.query(PersonalityResult).order_by(PersonalityResult.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "user_identifier": r.user_identifier,
            "user_id": str(r.user_id) if r.user_id else None,
            "dominant": r.dominant,
            "scores": r.scores,
            "answered": r.answered,
            "total_questions": r.total_questions,
            "created_at": r.created_at.isoformat(),
            "summary": r.summary,
        }
        for r in rows
    ]
