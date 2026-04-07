# utils/normalize.py
from __future__ import annotations
import re
from typing import Dict, List, Tuple, Optional

# ---------------------------
# Work mode / job type inference
# ---------------------------
def infer_work_mode(text: str, hint: Optional[bool] = None) -> str:
    t = (text or "").lower()
    if hint is True or any(x in t for x in ["remote", "work from home", "wfh", "home-based", "home based"]):
        return "remote"
    if "hybrid" in t or "partly remote" in t:
        return "hybrid"
    return "onsite"

def infer_job_type(text: str, hint: Optional[str] = None) -> str:
    t = (text or "").lower()
    h = (hint or "").lower()

    # map common hint values from APIs
    hint_map = {
        "full_time": "full_time",
        "full-time": "full_time",
        "permanent": "full_time",
        "part_time": "part_time",
        "part-time": "part_time",
        "intern": "internship",
        "internship": "internship",
        "contract": "contract",
        "temporary": "contract",
        "freelance": "freelance",
        "self-employed": "freelance",
    }
    if h in hint_map:
        return hint_map[h]

    # title/description patterns (use word boundaries)
    if re.search(r"\b(intern|internship|trainee|graduate)\b", t):
        return "internship"
    if re.search(r"\bpart[-\s]?time\b", t):
        return "part_time"
    if re.search(r"\bcontract|temporary|temp\b", t):
        return "contract"
    if re.search(r"\bfreelance|gig|independent contractor\b", t):
        return "freelance"
    if re.search(r"\bfull[-\s]?time|permanent\b", t):
        return "full_time"
    return "full_time"

# ---------------------------
# Salary formatting
# ---------------------------
def _salary_str(a: Optional[float], b: Optional[float]) -> str:
    if a and b:
        return f"PKR {int(a):,}–{int(b):,}"
    if a:
        return f"PKR {int(a):,}"
    if b:
        return f"PKR {int(b):,}"
    return ""

# ---------------------------
# Skills extraction
# ---------------------------
# Expand/adjust anytime
_SKILLS = {
    # FE
    "react", "javascript", "typescript", "html", "css", "tailwind", "redux",
    # BE
    "python", "django", "flask", "fastapi", "node", "express", "java", "spring", "kotlin",
    "c#", ".net", "dotnet", "php", "laravel", "go", "golang", "ruby", "rails",
    # data
    "sql", "mysql", "postgres", "postgresql", "mongodb", "excel", "power bi", "tableau",
    "pandas", "numpy", "scikit-learn", "machine learning", "ml", "nlp",
    # devops/cloud
    "git", "docker", "kubernetes", "aws", "azure", "gcp",
}

def _contains_token(text: str, token: str) -> bool:
    # use word boundaries where possible; allow spaces in multi-word tokens
    if " " in token:
        # for phrases like "power bi", "machine learning"
        pattern = r"\b" + re.escape(token) + r"\b"
    else:
        pattern = r"\b" + re.escape(token) + r"\b"
    return re.search(pattern, text) is not None

# utils/normalize.py
def extract_skills(text: str, title: str = "", user_skills: list[str] | None = None) -> list[str]:
    """Prefer user-provided skills; detect only those in the job text."""
    blob = f"{title} {text}".lower()
    if user_skills:
        hits = []
        for s in user_skills:
            s = (s or "").strip().lower()
            if not s: 
                continue
            # word boundary for single words; substring for phrases
            pattern = r"\b" + re.escape(s) + r"\b" if " " not in s else re.escape(s)
            if re.search(pattern, blob):
                hits.append(s)
        # de-dup preserving order
        seen, out = set(), []
        for h in hits:
            if h not in seen:
                out.append(h); seen.add(h)
        return out
    return []  # if none provided, skip (or fall back to a taxonomy)

# ---------------------------
# Normalize one job record
# ---------------------------
def normalize_job(j: Dict) -> Dict:
    title = (j.get("title") or "").strip()
    company = (j.get("company") or "").strip()
    location = (j.get("location") or "").strip()
    desc = (j.get("description") or "").strip()
    work_mode = infer_work_mode(desc, j.get("work_mode_hint"))
    job_type  = infer_job_type(f"{title} {desc}", j.get("job_type_hint"))
    salary = j.get("salary") or _salary_str(j.get("salary_min"), j.get("salary_max"))

    return {
        "source": j.get("source", "") or "",
        "title": title,
        "company": company,
        "location": location,
        "work_mode": work_mode,
        "job_type": job_type,
        "salary": salary,
        "salary_min": j.get("salary_min"),
        "salary_max": j.get("salary_max"),
        "apply_url": j.get("apply_url") or "",
        "description": desc,
        "skills": extract_skills(desc, title),
    }

# ---------------------------
# Dedupe
# ---------------------------
def _norm_key(*parts: str) -> str:
    joined = " ".join([p.lower().strip() for p in parts if p])
    # collapse spaces & drop punctuation for stable keys
    joined = re.sub(r"[\W_]+", " ", joined)
    return re.sub(r"\s+", " ", joined).strip()

def dedupe_jobs(items: List[Dict]) -> List[Dict]:
    seen = set()
    uniq = []
    for j in items:
        base_key = _norm_key(j.get("title",""), j.get("company",""), j.get("location",""))
        if not base_key and j.get("apply_url"):
            base_key = _norm_key(j["apply_url"])
        if base_key not in seen:
            uniq.append(j)
            seen.add(base_key)
    return uniq
