from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from recommender.similarity import text_cosine
from recommender.preprocessing import normalize_terms
from core import providers as P

router = APIRouter(prefix="/recommendations", tags=["jobs"])

class JobReq(BaseModel):
    skills: List[str] = Field(default_factory=list)
    skills_text: Optional[str] = None  # allow comma string too
    location: Optional[str] = "Karachi, Pakistan"
    limit: int = Field(default=20, ge=1, le=50)
    include_live: bool = True
    remote_only: bool = False
    employment_types: List[str] = Field(default_factory=list)  # e.g., ["full-time","part-time","internship"]

def passes_employment_filters(job: Dict[str, Any], types: List[str]) -> bool:
    if not types: return True
    text = " ".join([
        str(job.get("title","")), str(job.get("description","")),
        " ".join(job.get("tags") or [])
    ]).lower()
    keywords = {
        "full-time": ["full time","full-time","fulltime"],
        "part-time": ["part time","part-time","parttime"],
        "contract":  ["contract","freelance","consultant"],
        "internship":["intern","internship"],
    }
    return any(any(k in text for k in keywords.get(t, [])) for t in types)

@router.post("/jobs")
def jobs(req: JobReq) -> Dict[str, Any]:
    skills = req.skills or []
    if req.skills_text:
        skills += [s.strip() for s in req.skills_text.split(",") if s.strip()]

    if not skills:
        raise HTTPException(400, "Provide skills (array or skills_text)")

    query = " ".join(skills)

    # collect
    counts = {}
    jobs: List[Dict[str, Any]] = []

    def add(src, arr):
        counts[src] = len(arr)
        jobs.extend(arr)

    from core.providers import remotive, remoteok, jooble, jsearch

    add("remotive", remotive(query, 80))
    add("remoteok", remoteok(query, 80))
    if req.include_live:
        add("jooble",  jooble(query, req.location, 80))
        add("jsearch", jsearch(query, req.location, 80))

    # filter remote only / employment types
    filtered = []
    for j in jobs:
        if req.remote_only and not j.get("remote"): 
            continue
        if not passes_employment_filters(j, req.employment_types):
            continue
        filtered.append(j)

    q_terms = normalize_terms(skills)
    ranked=[]
    for j in filtered:
        doc_parts = [j.get("title",""), j.get("company",""), j.get("description","")] + list(map(str, j.get("tags") or []))
        sim = text_cosine(q_terms, doc_parts)
        loc_bonus = 0.25 if (req.location and (req.location.split(",")[0].lower() in str(j.get("location","")).lower())) else 0.0
        remote_bonus = 0.15 if j.get("remote") else 0.0
        score = float(2.0*sim + loc_bonus + remote_bonus)
        ranked.append({**j, "score": round(score,3)})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    top = ranked[:req.limit]

    return {
        "results": top,
        "meta": {
            "considered_total": len(jobs),
            "considered_after_filters": len(filtered),
            "per_provider": counts,
            "providers_enabled": P.providers_status(),
            "location": req.location,
            "skills": skills,
            "remote_only": req.remote_only,
            "employment_types": req.employment_types
        }
    }
