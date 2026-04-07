# app/api.py
from __future__ import annotations

import re
import os
import sys
import tempfile
import json, random
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Query,
    Form,
    Body,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import EmailStr, BaseModel
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

# ---- project root on sys.path ----
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# ---- local imports ----
from tools.parse_ocr_to_json import parse_pdf_to_json
from app.recommend import recommend_from_profile
from app.models import UserProfile, ResumeData, PsychometricResult  # Pydantic (Mongo shape)
from app.services import (
    save_user_profile,                # save_user_profile(profile, user_id=...)
    get_user_profile_by_user_id,      # unified profile from Mongo (by user_id)
    get_user_profile_by_email,        # unified profile from Mongo (by email)
)

# 🔐 Auth + DB (Postgres)
from app.db_pg import engine, get_pg
from app.models_pg import Base, User, PersonalityResult, AptitudeResult
from app.auth_router import router as auth_router
from app.deps import get_current_user

# ------------------------------------------------------------------------------------
# App init + CORS
# ------------------------------------------------------------------------------------
def _safe_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        EmailStr(value)
        return value
    except Exception:
        return None


app = FastAPI(
    title="CareerNexus Resume Parser API",
    description="Resumes + Profiles + Psychometric + Aptitude",
    version="1.3.2",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later (e.g., ["http://localhost:3000"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create PG tables on startup (dev convenience; use Alembic in prod)
@app.on_event("startup")
def _create_all_tables() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass

# ------------------------------------------------------------------------------------
# ✅ Mongo (LAZY + SAFE)
# ------------------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
MONGO_DB = os.getenv("MONGO_DB", "career_nexus")

_mongo_client: Optional[MongoClient] = None
_mdb = None
_profiles = None

def _get_mdb():
    """
    Lazy connect to Mongo so app doesn't crash on import.
    If Atlas DNS fails, return clean 503 instead of 500 stacktrace.
    """
    global _mongo_client, _mdb
    if _mdb is not None:
        return _mdb

    try:
        _mongo_client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=8000,
            connectTimeoutMS=8000,
            socketTimeoutMS=8000,
        )
        _mongo_client.admin.command("ping")  # test
        _mdb = _mongo_client[MONGO_DB]
        return _mdb
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"MongoDB not reachable. Check DNS / Atlas Network Access / MONGO_URI. Error: {str(e)}",
        )

def _get_profiles():
    global _profiles
    if _profiles is not None:
        return _profiles
    db = _get_mdb()
    _profiles = db["resumes"]
    return _profiles

@app.on_event("startup")
def _ensure_mongo_indexes() -> None:
    """
    Make indexes only if Mongo is reachable.
    """
    try:
        db = _get_mdb()
        db.resumes.create_index([("user_id", 1)], unique=True)
        db.user_profiles.create_index([("user_id", 1)], unique=True)
        db.resumes.create_index([("email", 1)], unique=False)
        db.user_profiles.create_index([("email", 1)], unique=False)
    except Exception:
        # don't crash server if Mongo is down
        pass

# ------------------------------------------------------------------------------------
# Health
# ------------------------------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


SUMMARY_HEADINGS = [
    "summary",
    "professional summary",
    "profile",
    "about",
    "about me",
    "introduction",
    "objective",
    "career objective",
    "personal statement",
    "overview",
    "professional profile",
]

EDUCATION_HEADINGS = [
    "education",
    "education and training",
    "academic background",
    "academic qualifications",
    "educational qualifications",
    "academic history",
    "academic profile",
    "education background",
    "qualifications",
    "academics",
]


SKILLS_HEADINGS = [
    "skills",
    "technical skills",
    "core skills",
    "key skills",
    "skill set",
    "skillset",
    "core competencies",
    "professional skills",
    "areas of expertise",
    "expertise",
    "technical competencies",
    "language skills",
]

PROJECTS_HEADINGS = [
    "projects",
    "academic projects",
    "professional projects",
    "key projects",
    "selected projects",
    "major projects",
    "research projects",
    "industry projects",
    "capstone projects",
    "notable projects",
]

CERTIFICATIONS_HEADINGS = [
    "certifications",
    "certification",
    "professional certifications",
    "certifications and licenses",
    "licenses",
    "training",
    "training and certifications",
    "courses",
    "courses and certifications",
    "workshops",
    "additional certifications",
    "additional qualifications",
    "additional qualification",
]



EXPERIENCE_HEADINGS = [
    "experience",
    "professional experience",
    "work experience",
    "employment history",
    "employment",
    "relevant experience",
    "industry experience",
    "academic experience",
    "teaching experience",
    "research experience",
    "professional background",
]


SECTION_STOP_HEADINGS = [
    # summary / profile
    "summary", "professional summary", "profile", "about", "about me",
    "objective", "career objective", "personal statement",

    # experience
    "experience", "professional experience", "work experience",
    "employment history", "employment", "relevant experience",
    "industry experience", "academic experience", "teaching experience",
    "research experience", "professional background",

    # education
    "education", "education and training", "academic background",
    "academic qualifications", "qualifications",

    # skills
    "skills", "technical skills", "core skills", "core competencies",
    "areas of expertise",

    # projects
    "projects", "academic projects", "professional projects",
    "research projects", "capstone projects",

    # certifications
    "certifications", "certification", "licenses", "training",
    # Additional qualifications should stop a section as well
    "additional qualifications", "additional qualification",

    # misc
    "publications", "languages", "interests",
    "achievements", "awards",
    "references", "contact",
]



def _norm_head(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", (s or "").strip().lower())

def _extract_section_text(raw_text: str, heading_list: list[str]) -> str:
    """
    Extract text under headings like 'About Me', 'Introduction', 'Objective', etc.
    Works on plain text by scanning line-by-line.
    """
    if not raw_text:
        return ""

    lines = [ln.strip() for ln in raw_text.splitlines()]
    lines = [ln for ln in lines if ln]  # remove empty

    # normalize heading sets
    want = {_norm_head(h) for h in heading_list}
    stop = {_norm_head(h) for h in SECTION_STOP_HEADINGS}

    collected: list[str] = []
    capturing = False

    for ln in lines:
        low = _norm_head(ln)

        # start capture if line is exactly a heading or looks like "ABOUT ME:"
        if low in want or any(low.startswith(h + " ") or low.startswith(h + ":") for h in want):
            capturing = True
            continue


        # stop capture if another main section starts
        if capturing and (low in stop or any(low.startswith(h + " ") or low.startswith(h + ":") for h in stop)):
            break

        if capturing:
            # avoid capturing emails/phones/links
            if "@" in ln or "http" in ln.lower():
                continue
            collected.append(ln)

            # safety: don't collect too much
            if len(" ".join(collected)) > 900:
                break

    text = " ".join(collected).strip()
    return text

def _merge_summary(existing: str, extra: str) -> str:
    existing = (existing or "").strip()
    extra = (extra or "").strip()

    if not extra:
        return existing

    if not existing:
        return extra

    # simple duplicate check
    if extra.lower() in existing.lower():
        return existing

    return (existing + "\n" + extra).strip()


# ------------------------------------------------------------------------------------
# Helpers (resume flatten/expand/backfill)
# ------------------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?:(?:\+?92|0)?\s*[-.]?\s*)?(?:3\d{2})\s*[-.\s]?\s*\d{7}\b"   # Pakistan mobile
    r"|(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b"  # generic
)
def _extract_inline_heading_value(raw_text: str, heading_list: list[str]) -> str:
    """
    Extract inline 'Heading: value' on the SAME line.
    Example: 'Certifications: Advance Diploma in IT.'
    Returns only the value part.
    """
    if not raw_text:
        return ""

    want = {_norm_head(h) for h in heading_list}

    for ln in [l.strip() for l in raw_text.splitlines() if l.strip()]:
        if ":" not in ln:
            continue
        left, right = ln.split(":", 1)
        if _norm_head(left) in want and right.strip():
            return right.strip()

    return ""


BAD_NAME_WORDS = {
    "resume", "cv", "curriculum", "vitae",
    "summary", "objective", "profile",
    "experience", "education", "skills", "projects",
    "certifications", "references",
    "computer", "science", "engineering",
    "undergraduate", "graduate", "student", "intern",
}

def _is_probably_not_name(line: str) -> bool:
    low = (line or "").strip().lower()
    if not low:
        return True
    if "@" in line or "http" in low:
        return True
    if any(ch.isdigit() for ch in line):
        return True

    # If line contains separators like | - , try taking left side as name
    # (handled in _pick_name_from_lines below)
    return False


def _pick_name_from_lines(lines: list[str]) -> Optional[str]:
    for ln in lines:
        ln = (ln or "").strip()
        if not ln:
            continue

        # If "Name | Title" => take left part
        if "|" in ln:
            ln = ln.split("|", 1)[0].strip()

        # basic skips
        if _is_probably_not_name(ln):
            continue

        low = ln.lower()
        if any(bad in low for bad in BAD_NAME_WORDS):
            # allow if it still looks like a name: 2-4 words and mostly letters
            words = ln.split()
            if not (2 <= len(words) <= 4):
                continue

        words = ln.split()
        if 1 < len(words) <= 4:
            return ln.title() if ln.isupper() else ln

    return None


def _extract_header_lines_from_pdf(pdf_path: str, *, top_ratio: float = 0.2) -> list[str]:
    """Return lines from the top of page 1 (works without pdfplumber)."""
    try:
        import fitz
        from collections import defaultdict
        doc = fitz.open(pdf_path)
        page = doc[0]
        height = page.rect.y1
        cutoff = height * top_ratio
        words = page.get_text("words") or []
        top_words = [w for w in words if w[1] <= cutoff]
        if not top_words:
            # fall back to page text if necessary
            return [l.strip() for l in page.get_text().splitlines()[:10] if l.strip()]
        buckets = defaultdict(list)
        for x0, y0, x1, y1, text, block_no, line_no, word_no in top_words:
            buckets[line_no].append((x0, text))
        header_lines = []
        for line_no in sorted(buckets.keys()):
            ws = sorted(buckets[line_no], key=lambda v: v[0])
            header_lines.append(" ".join([w for _, w in ws]))
        return header_lines[:10]
    except Exception:
        return []


def _extract_best_name(raw_text: str, pdf_path: str) -> Optional[str]:
    # 1) Best: header (PyMuPDF blocks)
    name_from_header = extract_first_name_from_header(pdf_path)
    if name_from_header:
        return name_from_header

    # 2) Next: header lines from words grouping (still good)
    header_lines = _extract_header_lines_from_pdf(pdf_path)
    name = _pick_name_from_lines(header_lines)
    if name:
        return name

    # 3) Fallback: raw text top lines
    lines = [l.strip() for l in (raw_text or "").splitlines() if l.strip()]
    return _pick_name_from_lines(lines[:30])



def _extract_email_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = _EMAIL_RE.search(text)
    return m.group(0).lower() if m else None

def _extract_phone_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = _PHONE_RE.search(text)
    if not m:
        return None
    phone = re.sub(r"[^\d+]", "", m.group(0))
    return phone

def _extract_name_from_resume_start(text: str) -> Optional[str]:
    """
    Extract name from the very beginning of resume.
    Assumes name is in first few lines.
    """
    if not text:
        return None

    BAD_WORDS = {
        "resume", "curriculum", "vitae", "cv",
        "summary", "objective", "profile",
        "experience", "education", "skills",
        "projects", "certifications",
        "computer", "science", "engineering",
        "undergraduate", "graduate", "student"
    }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for ln in lines[:5]:  # 🔥 only top of resume
        low = ln.lower()

        # skip emails, phones, links
        if "@" in ln or "http" in low:
            continue
        if any(ch.isdigit() for ch in ln):
            continue

        words = ln.split()
        if not (2 <= len(words) <= 4):
            continue

        # reject headings/titles
        if any(b in low for b in BAD_WORDS):
            continue

        # ACCEPT
        if ln.isupper():
            return ln.title()

        if all(w[0].isupper() for w in words):
            return ln

    return None


def _looks_like_title(s: Optional[str]) -> bool:
    if not s:
        return True
    low = s.strip().lower()
    bad = [
        "undergraduate", "graduate", "student", "intern",
        "engineer", "developer", "computer science", "software",
        "summary", "education", "experience", "skills", "projects",
    ]
    return any(k in low for k in bad)

def _extract_text_from_pdf(path: str) -> str:
    """
    Fallback: direct PDF text (first 2 pages).
    First try PyMuPDF (fitz) because it's usually available.
    Then fallback to pdfplumber if installed.
    """
    # 1) Try PyMuPDF
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        chunks = []
        for i in range(min(2, doc.page_count)):
            t = doc[i].get_text() or ""
            if t.strip():
                chunks.append(t)
        return "\n".join(chunks)
    except Exception:
        pass

    # 2) Fallback: pdfplumber (if available)
    try:
        import pdfplumber
        chunks = []
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages[:2]:
                t = p.extract_text() or ""
                if t.strip():
                    chunks.append(t)
        return "\n".join(chunks)
    except Exception:
        return ""


import fitz

def extract_first_name_from_header(pdf_path: str) -> Optional[str]:
    """
    Strong name extractor from top of page 1 using PyMuPDF (fitz).
    - Reads top area blocks
    - Picks first line that looks like a real name
    """
    try:
        import fitz  # PyMuPDF
    except Exception:
        return None

    try:
        doc = fitz.open(pdf_path)
        page = doc[0]

        # blocks: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = sorted(page.get_text("blocks") or [], key=lambda b: b[1])  # sort by y0 (top first)

        candidate_lines: list[str] = []
        for b in blocks[:12]:
            text = (b[4] or "").strip()
            if not text:
                continue
            for line in text.splitlines():
                line = line.strip()
                if line:
                    candidate_lines.append(line)

        # Use your existing filters
        name = _pick_name_from_lines(candidate_lines)
        if name:
            return name

        return None
    except Exception:
        return None




def _flatten(prefix: str, data: Dict[str, Any], out: Dict[str, Any]) -> None:
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            _flatten(key, v, out)
        else:
            out[key] = v

def _build_set_update(changes: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    _flatten("", changes, flat)
    return {"$set": flat} if flat else {}

def _denormalize_for_resumes(changes: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(changes, dict):
        return changes
    resume = changes.get("resume")
    if isinstance(resume, dict):
        for key in ("skills", "education", "experience", "summary", "projects", "certifications"):
            if key in resume and resume[key] is not None:
                changes[key] = resume[key]
    return changes

def _expand_resume_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc or {})
    out.pop("_id", None)
    resume_block = {
        "summary": out.get("summary") or "",
        "experience": out.get("experience") or "",
        "education": out.get("education") or [],
        "projects": out.get("projects") or [],
        "skills": out.get("skills") or [],
        "certifications": out.get("certifications") or [],
    }
    out["resume"] = resume_block
    return out

def _backfill_from_flat(profile: dict, *, email: str | None = None, user_id: str | None = None) -> dict:
    if not profile:
        return profile

    db = _get_mdb()
    flat = None
    if user_id:
        flat = db.resumes.find_one({"user_id": user_id})
    if not flat and email:
        flat = db.resumes.find_one({"email": (email or "").lower()})
    if not flat:
        return profile

    profile.setdefault("resume", {})
    r = profile["resume"]

    def use(field: str):
        cur = r.get(field)
        if cur in (None, "") or (isinstance(cur, list) and len(cur) == 0):
            val = flat.get(field)
            if val:
                r[field] = val

    for field in ("summary", "experience", "skills", "education", "projects", "certifications"):
        use(field)

    return profile

# ------------------------------------------------------------------------------------
# 🔧 PATCH models (needed for /profile/me PATCH)
# ------------------------------------------------------------------------------------
class ResumeDataUpdate(BaseModel):
    summary: Optional[str] = None
    experience: Optional[str] = None
    education: Optional[list[str]] = None
    projects: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    certifications: Optional[list[str]] = None

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    resume: Optional[ResumeDataUpdate] = None
    psychometric_result: Optional[dict] = None
    psychometric: Optional[dict] = None

try:
    ResumeDataUpdate.model_rebuild()
    UserProfileUpdate.model_rebuild()
except Exception:
    pass

# ------------------------------------------------------------------------------------
# JWT-protected, user_id-based profile + resume endpoints
# ------------------------------------------------------------------------------------
@app.get("/profile/me", response_model=dict)
async def get_my_profile(current: User = Depends(get_current_user)):
    uid = str(current.id)
    profiles = _get_profiles()

    flat = profiles.find_one({"user_id": uid})
    if flat:
        flat.pop("_id", None)
        return _expand_resume_view(flat)

    unified = await get_user_profile_by_user_id(uid)
    if not unified:
        raise HTTPException(status_code=404, detail="Profile not found")

    unified = _backfill_from_flat(unified, user_id=uid, email=(current.email or "").lower())
    resume_u = unified.get("resume") or {}
    flattened = {
        "user_id": uid,
        "email": unified.get("email"),
        "name": unified.get("name"),
        "phone": unified.get("phone"),
        "summary": resume_u.get("summary") or "",
        "experience": resume_u.get("experience") or "",
        "skills": resume_u.get("skills") or [],
        "education": resume_u.get("education") or [],
        "projects": resume_u.get("projects") or [],
        "certifications": resume_u.get("certifications") or [],
    }
    return _expand_resume_view(flattened)

# ✅ MODIFIED ENDPOINT #1
# - PATCH /profile/me now ALSO syncs into db.user_profiles (unified doc)
@app.patch("/profile/me")
async def patch_my_profile(
    payload: UserProfileUpdate = Body(...),
    current: User = Depends(get_current_user),
):
    uid = str(current.id)
    changes = payload.dict(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")

    db = _get_mdb()
    profiles = _get_profiles()

    changes = _denormalize_for_resumes(changes)
    update_doc = _build_set_update(changes)
    update_doc.setdefault("$set", {})
    update_doc["$set"]["user_id"] = uid
    update_doc["$set"]["email"] = (current.email or "").lower()

    # 1) update resumes flat doc (used by /profile/me)
    profiles.update_one({"user_id": uid}, update_doc, upsert=True)

    # 2) sync unified doc in user_profiles (used by /profile/full/me + other services)
    try:
        flat = profiles.find_one({"user_id": uid}) or {}
        resume_block = {
            "summary": flat.get("summary") or "",
            "experience": flat.get("experience") or "",
            "education": flat.get("education") or [],
            "projects": flat.get("projects") or [],
            "skills": flat.get("skills") or [],
            "certifications": flat.get("certifications") or [],
        }

        unified_update = {
            "user_id": uid,
            "email": (current.email or "").lower(),
            "name": flat.get("name") or changes.get("name") or (current.first_name or current.name),
            "phone": flat.get("phone") or changes.get("phone"),
            "resume": resume_block,
            "updated_at": datetime.utcnow(),
        }

        db.user_profiles.update_one(
            {"user_id": uid},
            {"$set": unified_update},
            upsert=True,
        )
    except Exception as e:
        # don't fail patch in dev
        print("[sync user_profiles] failed:", e)

    return {"message": "Profile updated successfully"}

# ------------------------------------------------------------------------------------
# Parse a PDF and return JSON (OCR + sectionizer)
# ------------------------------------------------------------------------------------
@app.post("/parse-resume")
async def parse_resume(file: UploadFile = File(...)) -> Dict[str, Any]:
    content_type = (file.content_type or "").lower()
    if not (content_type.endswith("/pdf") or file.filename.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Unsupported file type. Please upload a PDF.")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e!s}")

    try:
        result = parse_pdf_to_json(tmp_path)

        # ✅ ADD HERE (right after parse_pdf_to_json)
        raw_text = (result.get("raw_text") or result.get("text") or result.get("full_text") or "")

        pdf_text = _extract_text_from_pdf(tmp_path)
        if pdf_text:
            if not raw_text or len(raw_text.strip()) < 200:
                raw_text = pdf_text
            else:
                raw_text = raw_text + "\n" + pdf_text

        if not result.get("email"):
            result["email"] = _safe_email(_extract_email_from_text(raw_text))

        if not result.get("phone"):
            result["phone"] = _extract_phone_from_text(raw_text)

        if not result.get("name"):
            result["name"] = _extract_best_name(raw_text, tmp_path)
        # ✅ END ADD

        # ✅ Merge About/Profile/Intro/Objective => summary
        extra_summary = _extract_section_text(raw_text, SUMMARY_HEADINGS)
        result["summary"] = _merge_summary(result.get("summary") or "", extra_summary)

        if not (result.get("experience") or "").strip():
            result["experience"] = _extract_section_text(raw_text, EXPERIENCE_HEADINGS)

        # ✅ Education
        if not result.get("education"):
            edu_text = _extract_section_text(raw_text, EDUCATION_HEADINGS)
            if edu_text:
                result["education"] = [edu_text]

        # ✅ Skills
        if not result.get("skills"):
            skills_text = _extract_section_text(raw_text, SKILLS_HEADINGS)
            if skills_text:
                result["skills"] = [s.strip() for s in skills_text.split(",") if s.strip()]

        # ✅ Projects
        if not result.get("projects"):
            proj_text = _extract_section_text(raw_text, PROJECTS_HEADINGS)
            if proj_text:
                result["projects"] = [proj_text]

        # ✅ Certifications 
        if not result.get("certifications"):
            inline_cert = _extract_inline_heading_value(raw_text, CERTIFICATIONS_HEADINGS)
            if inline_cert:
                result["certifications"] = [inline_cert]
            else:
                cert_text = _extract_section_text(raw_text, CERTIFICATIONS_HEADINGS)
                if cert_text:
                    result["certifications"] = [cert_text]




        if not result or ("error" in result and result["error"]):
            raise HTTPException(status_code=422, detail=result.get("error", "Unable to parse resume."))

        result["filename"] = file.filename
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing error: {e!s}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    
    

# ------------------------------------------------------------------------------------
# Auth-required: Upload PDF and immediately SAVE a merged UserProfile for current user
# ------------------------------------------------------------------------------------
@app.post("/ingest-resume")
async def ingest_resume(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    personality_type: Optional[str] = Form(None),
    aptitude_score: Optional[str] = Form(None),
    current: User = Depends(get_current_user),
) -> Dict[str, Any]:
    content_type = (file.content_type or "").lower()
    if not (content_type.endswith("/pdf") or file.filename.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Unsupported file type. Please upload a PDF.")

    def _clean_form(v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        if v == "" or v.lower() == "string":
            return None
        return v

    name = _clean_form(name)
    phone = _clean_form(phone)
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e!s}")

    try:
        db = _get_mdb()
        profiles = _get_profiles()

        parsed = parse_pdf_to_json(tmp_path) or {}
        if "error" in parsed and parsed["error"]:
            raise HTTPException(status_code=422, detail=parsed["error"])

        # -------------------- ✅ robust extraction fallback --------------------
        raw_text = (parsed.get("raw_text") or parsed.get("text") or parsed.get("full_text") or "")

        # ✅ fallback: agar parser ne header miss kiya ho
        pdf_text = _extract_text_from_pdf(tmp_path)
        if pdf_text:
            # if raw_text empty/short, prefer pdf_text; else append
            if not raw_text or len(raw_text.strip()) < 200:
                raw_text = pdf_text
            else:
                raw_text = raw_text + "\n" + pdf_text



        # --- normalize possible keys from parser ---
        parsed_email = _safe_email(parsed.get("email")) or _extract_email_from_text(raw_text)
        parsed_phone = (
            parsed.get("phone")
            or parsed.get("contact")
            or parsed.get("mobile")
            or parsed.get("phone_number")
            or _extract_phone_from_text(raw_text)
        )
        parsed_name = _extract_best_name(raw_text, tmp_path)

        # ✅ Merge About/Profile/Intro/Objective => summary
        extra_summary = _extract_section_text(raw_text, SUMMARY_HEADINGS)
        parsed["summary"] = _merge_summary(parsed.get("summary") or "", extra_summary)

        if not (parsed.get("experience") or "").strip():
            parsed["experience"] = _extract_section_text(raw_text, EXPERIENCE_HEADINGS)

        # ✅ Education
        if not parsed.get("education"):
            edu_text = _extract_section_text(raw_text, EDUCATION_HEADINGS)
            if edu_text:
                parsed["education"] = [edu_text]

        # ✅ Skills
        if not parsed.get("skills"):
            skills_text = _extract_section_text(raw_text, SKILLS_HEADINGS)
            if skills_text:
                parsed["skills"] = [s.strip() for s in skills_text.split(",") if s.strip()]

        # ✅ Projects
        if not parsed.get("projects"):
            proj_text = _extract_section_text(raw_text, PROJECTS_HEADINGS)
            if proj_text:
                parsed["projects"] = [proj_text]

        # ✅ Certifications
        if not parsed.get("certifications"):
            inline = _extract_inline_heading_value(raw_text, CERTIFICATIONS_HEADINGS)
            if inline:
                parsed["certifications"] = [inline]
            else:
                cert_text = _extract_section_text(raw_text, CERTIFICATIONS_HEADINGS)
                if cert_text:
                    parsed["certifications"] = [cert_text]


        # ----------------------------------------------------------------------


        resume_data = ResumeData(
            summary=parsed.get("summary"),
            experience=parsed.get("experience"),
            education=parsed.get("education") or [],
            projects=parsed.get("projects") or [],
            skills=parsed.get("skills") or [],
            certifications=parsed.get("certifications") or [],
        )

        merged_name = parsed_name or name or (current.first_name or current.name)



        merged_email = parsed_email or current.email # keep auth as source of truth
        merged_phone = phone or parsed_phone


        score_value: Optional[int] = None
        if aptitude_score is not None and str(aptitude_score).strip() != "":
            try:
                score_value = int(str(aptitude_score).strip())
            except ValueError:
                score_value = None

        psychometric = None
        if personality_type or score_value is not None:
            psychometric = PsychometricResult(
                personality_type=personality_type,
                aptitude_score=score_value,
            )

        profile = UserProfile(
            name=merged_name,
            email=merged_email,
            phone=merged_phone,
            resume=resume_data,
            psychometric=psychometric,
        )

        uid = str(current.id)
        await save_user_profile(profile, user_id=uid)

        resume_doc = {
            "user_id": uid,
            "email": (current.email or "").lower(),      # auth email (identity)
            "resume_email": (parsed_email or "").lower(),
            "name": merged_name,
            "skills": resume_data.skills or [],
            "education": resume_data.education or [],
            "experience": resume_data.experience or "",
            "summary": resume_data.summary or "",
            "projects": resume_data.projects or [],
            "certifications": resume_data.certifications or [],
            "uploaded_at": datetime.utcnow(),
        }
        db.resumes.replace_one({"user_id": uid}, resume_doc, upsert=True)

        email_to_show = parsed_email

        return {
            "message": "User profile ingested successfully",
            "user_id": uid,
            "profile_preview": {
                "name": merged_name,
                "email": email_to_show,
                "phone": merged_phone,
                "skills_count": len(resume_data.skills or []),
                "projects_count": len(resume_data.projects or []),
            },
            "parsed_from_pdf": {
                "filename": file.filename,
                "summary_sample": (resume_data.summary or "")[:180],
            },

            "warning": None if email_to_show else "No email found in resume",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {e!s}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

# ------------------------------------------------------------------------------------
# Recommendations (JWT)
# ------------------------------------------------------------------------------------
@app.get("/recommendations/me")
async def get_my_recommendations(current: User = Depends(get_current_user)):
    profile = await get_user_profile_by_user_id(str(current.id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    careers = recommend_from_profile(profile, top_k=3)
    return {"recommended_careers": careers}

# ------------------------------------------------------------------------------------
# Unified profile (resume + psychometric + recommendations) by email
# ------------------------------------------------------------------------------------
@app.get("/profile/with-recs/by-email/{email}")
async def get_profile_with_recs(email: str, db: Session = Depends(get_pg)):
    email_l = (email or "").strip().lower()

    profile = await get_user_profile_by_email(email_l)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = _backfill_from_flat(profile, email=email_l)

    psy = None
    user = db.execute(select(User).where(User.email == email_l)).scalar_one_or_none()

    if user:
        q = (
            select(PersonalityResult)
            .where(PersonalityResult.user_id == user.id)
            .order_by(PersonalityResult.created_at.desc())
            .limit(1)
        )
        pr = db.execute(q).scalar_one_or_none()
        if not pr:
            q2 = (
                select(PersonalityResult)
                .where(PersonalityResult.user_identifier == email_l)
                .order_by(PersonalityResult.created_at.desc())
                .limit(1)
            )
            pr = db.execute(q2).scalar_one_or_none()
    else:
        q2 = (
            select(PersonalityResult)
            .where(PersonalityResult.user_identifier == email_l)
            .order_by(PersonalityResult.created_at.desc())
            .limit(1)
        )
        pr = db.execute(q2).scalar_one_or_none()

    if pr:
        psy = {
            "scores": pr.scores,
            "dominant": pr.dominant,
            "summary": pr.summary,
            "created_at": pr.created_at.isoformat(),
        }

    careers = []
    try:
        fused = dict(profile)
        if psy:
            fused["psychometric"] = {
                "scores": psy.get("scores"),
                "dominant": psy.get("dominant"),
                "summary": psy.get("summary"),
            }
        careers = recommend_from_profile(fused, top_k=3)
    except Exception as e:
        print(f"[recs] failed for {email_l}: {e!s}")

    profile.pop("psychometric", None)

    return {
        "email": email_l,
        "profile": profile,
        "psychometric_result": psy,
        "recommended_careers": careers,
    }

# ✅ MODIFIED ENDPOINT #2
# - /profile/full/me now reads unified profile by user_id (fallback email)
@app.get("/profile/full/me")
async def get_profile_with_recs_for_loggedin_user(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_pg),
):
    email_l = (current.email or "").strip().lower()
    uid = str(current.id)

    # ✅ prefer canonical unified profile by user_id
    profile = await get_user_profile_by_user_id(uid)

    # fallback legacy email-based profile (old data)
    if not profile:
        profile = await get_user_profile_by_email(email_l)

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = _backfill_from_flat(profile, email=email_l, user_id=uid)

    psy = None
    pr = (
        db.query(PersonalityResult)
        .filter(PersonalityResult.user_id == current.id)
        .order_by(PersonalityResult.created_at.desc())
        .first()
    )
    if not pr:
        pr = (
            db.query(PersonalityResult)
            .filter(PersonalityResult.user_identifier == email_l)
            .order_by(PersonalityResult.created_at.desc())
            .first()
        )
    if pr:
        psy = {
            "scores": pr.scores,
            "dominant": pr.dominant,
            "summary": pr.summary,
            "created_at": pr.created_at.isoformat(),
        }

    careers = []
    try:
        fused = dict(profile)
        if psy:
            fused["psychometric"] = {
                "scores": psy.get("scores"),
                "dominant": psy.get("dominant"),
                "summary": psy.get("summary"),
            }
        careers = recommend_from_profile(fused, top_k=3)
    except Exception as e:
        print(f"[recs] failed for {email_l}: {e!s}")

    profile.pop("psychometric", None)

    return {
        "email": email_l,
        "profile": profile,
        "psychometric_result": psy,
        "recommended_careers": careers,
    }

# ====================================================================================
#                               A P T I T U D E   A P I
# ====================================================================================

DATA_DIR = ROOT / "data"
APTITUDE_DATA_FILE = DATA_DIR / "aptitude_questions.json"

def _load_aptitude_bank():
    try:
        with open(APTITUDE_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Dataset not found at {APTITUDE_DATA_FILE}")

QUESTION_BANK = _load_aptitude_bank()
ALLOWED_DOMAINS = {q["domain"] for q in QUESTION_BANK}
ALLOWED_LEVELS = {"Intermediate", "Bachelors", "Masters"}

class AptitudeAnswers(BaseModel):
    answers: Dict[str, int]
    domain: Optional[str] = None
    level: Optional[str] = None

@app.get("/aptitude/domains", tags=["Aptitude"])
def aptitude_get_domains():
    return sorted(ALLOWED_DOMAINS)

@app.get("/aptitude/questions", tags=["Aptitude"])
def aptitude_get_questions(
    domain: str = Query(..., description="Example: CS, IT, SE (must match dataset domain)"),
    n: int = Query(6, ge=1, le=50),
    difficulty_min: int = Query(1, ge=1, le=5),
    difficulty_max: int = Query(5, ge=1, le=5),
    level: Optional[str] = Query(None, description="Intermediate | Bachelors | Masters"),
):
    d = domain.upper()
    if d not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {d}")

    pool = [q for q in QUESTION_BANK if q["domain"] == d and difficulty_min <= q.get("difficulty", 1) <= difficulty_max]

    if level:
        if level not in ALLOWED_LEVELS:
            raise HTTPException(status_code=400, detail=f"Invalid level: {level}")
        pool = [q for q in pool if q.get("level") == level]

    if not pool:
        raise HTTPException(status_code=404, detail="No matching questions found.")

    random.shuffle(pool)

    selected = [dict(q) for q in pool[:n]]
    for q in selected:
        q.pop("answer_idx", None)

    return {"domain": d, "count": len(selected), "questions": selected}

def _score_aptitude(payload: AptitudeAnswers) -> tuple[int, int, float, Dict[str, Dict[str, int | float]]]:
    by_id = {q["id"]: q for q in QUESTION_BANK}
    if not payload.answers:
        raise HTTPException(status_code=400, detail="No answers provided.")

    total = len(payload.answers)
    correct = 0
    topic_stats: Dict[str, Dict[str, int]] = {}

    for qid, sel in payload.answers.items():
        q = by_id.get(qid)
        if not q:
            continue
        topic = q["topic"]
        topic_stats.setdefault(topic, {"correct": 0, "total": 0})
        topic_stats[topic]["total"] += 1
        if sel == q.get("answer_idx"):
            correct += 1
            topic_stats[topic]["correct"] += 1

    percent = round(correct / total * 100, 1) if total else 0.0
    breakdown = {
        topic: {
            "correct": data["correct"],
            "total": data["total"],
            "percent": round((data["correct"] / data["total"]) * 100, 1) if data["total"] else 0.0,
        }
        for topic, data in topic_stats.items()
    }
    return correct, total, percent, breakdown

@app.post("/aptitude/score", tags=["Aptitude"])
def aptitude_calculate_score(payload: AptitudeAnswers):
    correct, total, percent, breakdown = _score_aptitude(payload)
    return {
        "domain": payload.domain,
        "level": payload.level,
        "correct": correct,
        "total": total,
        "percent": percent,
        "breakdown": breakdown,
        "note": "Not saved. Use /aptitude/score/me to persist.",
    }

@app.post("/aptitude/score/me", tags=["Aptitude"])
def aptitude_score_me(
    payload: AptitudeAnswers,
    db: Session = Depends(get_pg),
    current: User = Depends(get_current_user),
):
    correct, total, percent, breakdown = _score_aptitude(payload)

    row = AptitudeResult(
        user_id=current.id,
        domain=payload.domain,
        level=payload.level,
        total=total,
        correct=correct,
        percent=Decimal(str(percent)),
        breakdown=breakdown,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "attempt_id": row.id,
        "domain": row.domain,
        "level": row.level,
        "correct": row.correct,
        "total": row.total,
        "percent": float(row.percent),
        "breakdown": row.breakdown,
        "created_at": row.created_at.isoformat(),
        "note": "Saved to database (linked to user).",
    }

@app.get("/aptitude/results/me", tags=["Aptitude"])
def aptitude_my_results(
    db: Session = Depends(get_pg),
    current: User = Depends(get_current_user),
):
    rows = (
        db.query(AptitudeResult)
        .filter(AptitudeResult.user_id == current.id)
        .order_by(AptitudeResult.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "domain": r.domain,
            "level": r.level,
            "correct": r.correct,
            "total": r.total,
            "percent": float(r.percent),
            "breakdown": r.breakdown,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

@app.get("/aptitude/me/latest", tags=["Aptitude"])
def aptitude_my_latest_attempt(
    db: Session = Depends(get_pg),
    current: User = Depends(get_current_user),
):
    row = (
        db.query(AptitudeResult)
        .filter(AptitudeResult.user_id == current.id)
        .order_by(AptitudeResult.created_at.desc())
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="No aptitude attempts found")

    return {
        "id": row.id,
        "domain": row.domain,
        "level": row.level,
        "correct": row.correct,
        "total": row.total,
        "percent": float(row.percent),
        "breakdown": row.breakdown,
        "created_at": row.created_at.isoformat(),
    }

@app.get("/aptitude/me/history", tags=["Aptitude"])
def aptitude_my_attempt_history(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_pg),
    current: User = Depends(get_current_user),
):
    rows = (
        db.query(AptitudeResult)
        .filter(AptitudeResult.user_id == current.id)
        .order_by(AptitudeResult.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": r.id,
            "domain": r.domain,
            "level": r.level,
            "correct": r.correct,
            "total": r.total,
            "percent": float(r.percent),
            "breakdown": r.breakdown,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

# ------------------------------------------------------------------------------------
# Routers (auth)
# ------------------------------------------------------------------------------------
app.include_router(auth_router)
