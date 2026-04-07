import os, requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
load_dotenv()  # reads backend/.env if present

def providers_status() -> Dict[str, bool]:
    return {
        "remotive": True,
        "remoteok": True,
        "jooble": bool(os.environ.get("JOOBLE_API_KEY")),
        "jsearch": bool(os.environ.get("JSEARCH_API_KEY")),
    }

def remotive(query: str, limit: int=30) -> List[Dict[str, Any]]:
    try:
        r = requests.get("https://remotive.com/api/remote-jobs", params={"search": query}, timeout=20)
        r.raise_for_status()
        out=[]
        for j in r.json().get("jobs", [])[:limit]:
            out.append({
                "id": f"remotive:{j.get('id')}",
                "title": j.get("title"),
                "company": j.get("company_name"),
                "location": j.get("candidate_required_location"),
                "remote": True,
                "posted_at": j.get("publication_date"),
                "apply_url": j.get("url"),
                "tags": j.get("tags") or [],
                "description": j.get("description") or "",
                "source": "remotive",
            })
        return out
    except Exception:
        return []

def remoteok(query: str, limit: int=30) -> List[Dict[str, Any]]:
    try:
        r = requests.get("https://remoteok.com/api", headers={"User-Agent":"CareerNexus/1.0"}, timeout=20)
        r.raise_for_status()
        out=[]
        for d in r.json():
            if not isinstance(d, dict) or not d.get("position"): continue
            if query and query.lower() not in (d.get("position","").lower()): continue
            out.append({
                "id": f"remoteok:{d.get('id')}",
                "title": d.get("position"),
                "company": d.get("company"),
                "location": "Remote",
                "remote": True,
                "posted_at": d.get("date"),
                "apply_url": d.get("url"),
                "tags": d.get("tags") or [],
                "description": d.get("description") or "",
                "source": "remoteok",
            })
            if len(out) >= limit: break
        return out
    except Exception:
        return []

def jooble(query: str, location: Optional[str], limit: int=30) -> List[Dict[str, Any]]:
    key = os.environ.get("JOOBLE_API_KEY")
    if not key: return []
    try:
        payload = {"keywords": query, "page": 1}
        if location: payload["location"] = location
        r = requests.post(f"https://jooble.org/api/{key}", json=payload, timeout=20)
        r.raise_for_status()
        out=[]
        for j in r.json().get("jobs", [])[:limit]:
            out.append({
                "id": f"jooble:{j.get('id','')}",
                "title": j.get("title"),
                "company": j.get("company"),
                "location": j.get("location"),
                "remote": "remote" in (j.get("type") or "").lower(),
                "posted_at": j.get("updated"),
                "apply_url": j.get("link"),
                "tags": j.get("skills") or [],
                "description": j.get("snippet") or "",
                "source": "jooble",
            })
        return out
    except Exception:
        return []

def jsearch(query: str, location: Optional[str], limit: int=30) -> List[Dict[str, Any]]:
    key = os.environ.get("JSEARCH_API_KEY")
    if not key: return []
    try:
        params={"query": f"{query} in {location}" if location else query, "num_pages": 1}
        headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
        r = requests.get("https://jsearch.p.rapidapi.com/search", headers=headers, params=params, timeout=20)
        r.raise_for_status()
        out=[]
        for d in r.json().get("data", [])[:limit]:
            out.append({
                "id": f"jsearch:{d.get('job_id')}",
                "title": d.get("job_title"),
                "company": d.get("employer_name"),
                "location": d.get("job_city") or d.get("job_country"),
                "remote": bool(d.get("job_is_remote")),
                "posted_at": d.get("job_posted_at_datetime_utc"),
                "apply_url": d.get("job_apply_link") or d.get("job_apply_is_direct"),
                "tags": d.get("job_required_skills") or [],
                "description": d.get("job_description") or "",
                "source": "jsearch",
            })
        return out
    except Exception:
        return []
