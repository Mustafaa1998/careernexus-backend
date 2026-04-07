# services/job_aggregator.py
from __future__ import annotations
import os, httpx, asyncio, re
from typing import List, Dict
from bs4 import BeautifulSoup
from utils.normalize import normalize_job, dedupe_jobs

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CareerNexusBot/1.0"

def _get_env(name: str, default: str = "") -> str:
    # read env at call time (safer if .env was loaded after imports)
    return os.getenv(name, default).strip()

def _safe_location(loc: str | None) -> str:
    return (loc or "Pakistan").strip() or "Pakistan"

# ---------------------------
# ADZUNA (country: Pakistan)
# ---------------------------
ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/pk/search"

async def fetch_adzuna(query: str, location: str, page: int = 1):
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        print("Adzuna: missing keys")
        return []

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "where": location or "Pakistan",
        "results_per_page": 20,  # keep modest to avoid 429s
    }
    url = f"{ADZUNA_BASE}/{page}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, params=params)  # ✅ NO 'content-type' in params
            if r.status_code == 429:
                print("Adzuna 429: rate limited")
                return []
            if r.status_code != 200:
                print("Adzuna error:", r.status_code, r.text[:200])
                return []
            data = r.json()
            results = data.get("results", []) or []
            out = []
            for item in results:
                out.append({
                    "title": item.get("title", ""),
                    "company": (item.get("company") or {}).get("display_name", ""),
                    "location": (item.get("location") or {}).get("display_name", location),
                    "work_mode": "onsite",
                    "job_type": "full_time",
                    "salary": "",
                    "apply_url": item.get("redirect_url", ""),
                    "source": "adzuna",
                })
            return out
    except Exception as e:
        print("Adzuna exception:", repr(e))
        return []

# ---------------------------
# SerpAPI (Google Jobs)
# ---------------------------
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()

async def fetch_serpapi_google_jobs(query: str, location: str):
    """
    Fetch Google Jobs via SerpAPI.
    Returns a list of normalized job dicts (same fields you use elsewhere).
    On failure, prints detailed info and returns [] (does not raise).
    """
    if not SERPAPI_KEY:
        print("SerpAPI: missing SERPAPI_KEY")
        return []

    base = "https://serpapi.com/search.json"
    params = {
        "engine": "google_jobs",
        "q": f"{query} in {location}",
        "api_key": SERPAPI_KEY,
        "hl": "en",
        # "start": 0,  # optional paging
    }

    items = []
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(base, params=params, timeout=30.0)

        if r.status_code != 200:
            # Show *why* it failed (401/400/etc.) so we can fix quickly.
            print("SerpAPI status:", r.status_code)
            try:
                print("SerpAPI body:", r.text[:800])
            except Exception:
                pass
            return []

        data = r.json()
        jobs = data.get("jobs_results", []) or []

        for j in jobs:
            title = j.get("title") or ""
            company = j.get("company_name") or ""
            # SerpAPI often returns a localized string; keep it simple:
            loc = j.get("location") or location
            # Prefer first apply option link; otherwise share_link
            apply_url = None
            for opt in (j.get("apply_options") or []):
                if opt.get("link"):
                    apply_url = opt["link"]
                    break
            if not apply_url:
                apply_url = j.get("share_link")

            items.append({
                "title": title,
                "company": company,
                "location": loc,
                "work_mode": "remote" if "remote" in (j.get("description") or "").lower() else "",
                "job_type": "",
                "salary": "",
                "match": 0.0,     # your ranker will overwrite
                "apply_url": apply_url or "",
                "source": "serpapi",  # make it obvious these came from SerpAPI
            })

    except Exception as e:
        print("SerpAPI exception:", repr(e))
        return []

    return items
# ---------------------------
# Rozee.pk (light scrape)
# ---------------------------
async def fetch_rozee(query: str, location: str, page: int = 1) -> List[Dict]:
    q = re.sub(r"\s+", "+", (query or "").strip())
    url = f"https://www.rozee.pk/job/jsearch/q-{q}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0),
                                     headers={"User-Agent": UA}) as c:
            r = await c.get(url)
            if r.status_code != 200:
                print("Rozee status:", r.status_code)
                return []
            soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("Rozee error:", e)
        return []

    jobs = []
    # NOTE: selectors may change; adjust as needed
    for card in soup.select(".job-search-card"):
        title_el = card.select_one(".job-title a")
        comp_el  = card.select_one(".company-name")
        loc_el   = card.select_one(".job-locations")
        desc_el  = card.select_one(".job-text")
        link     = title_el["href"] if title_el and title_el.has_attr("href") else None
        jobs.append(normalize_job({
            "source": "rozee",
            "title": title_el.get_text(strip=True) if title_el else None,
            "company": comp_el.get_text(strip=True) if comp_el else None,
            "location": (loc_el.get_text(strip=True) if loc_el else _safe_location(location)),
            "description": desc_el.get_text(strip=True) if desc_el else "",
            "apply_url": f"https://www.rozee.pk{link}" if link and link.startswith("/") else link
        }))
    return jobs

# ---------------------------
# Mustakbil (light scrape)
# ---------------------------
async def fetch_mustakbil(query: str, location: str, page: int = 1) -> List[Dict]:
    q = re.sub(r"\s+", "%20", (query or "").strip())
    url = f"https://www.mustakbil.com/jobs/search?q={q}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0),
                                     headers={"User-Agent": UA}) as c:
            r = await c.get(url)
            if r.status_code != 200:
                print("Mustakbil status:", r.status_code)
                return []
            soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("Mustakbil error:", e)
        return []

    jobs = []
    for card in soup.select("div.job"):
        title_el = card.select_one("h2 a")
        comp_el  = card.select_one(".company")
        loc_el   = card.select_one(".location")
        desc_el  = card.select_one(".excerpt")
        link     = title_el["href"] if title_el and title_el.has_attr("href") else None
        jobs.append(normalize_job({
            "source": "mustakbil",
            "title": title_el.get_text(strip=True) if title_el else None,
            "company": comp_el.get_text(strip=True) if comp_el else None,
            "location": (loc_el.get_text(strip=True) if loc_el else _safe_location(location)),
            "description": desc_el.get_text(strip=True) if desc_el else "",
            "apply_url": f"https://www.mustakbil.com{link}" if link and link.startswith("/") else link
        }))
    return jobs

# ---------------------------
# Jooble
# ---------------------------
async def fetch_jooble(query: str, location: str, page: int = 1) -> List[Dict]:
    key = _get_env("JOOBLE_API_KEY")
    if not key:
        # print("Jooble: missing key")
        return []
    url = f"https://jooble.org/api/{key}"
    payload = {"keywords": query, "location": _safe_location(location), "page": page}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0),
                                     headers={"User-Agent": UA}) as c:
            r = await c.post(url, json=payload)
            r.raise_for_status()
            raw = r.json().get("jobs", [])
    except Exception as e:
        print("Jooble error:", e)
        return []
    jobs = []
    for j in raw:
        jobs.append(normalize_job({
            "source": "jooble",
            "title": j.get("title"),
            "company": j.get("company"),
            "location": j.get("location"),
            "description": j.get("snippet") or "",
            "salary": j.get("salary"),
            "apply_url": j.get("link")
        }))
    return jobs

# ---------------------------
# JSearch (RapidAPI)
# ---------------------------
async def fetch_jsearch(query: str, location: str, page: int = 1) -> List[Dict]:
    key = _get_env("JSEARCH_API_KEY")
    if not key:
        # print("JSearch: missing key")
        return []
    url = "https://jsearch.p.rapidapi.com/search"
    params = {"query": f"{query} in {_safe_location(location)}", "page": page, "num_pages": 1}
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0),
                                     headers={"User-Agent": UA, **headers}) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            raw = r.json().get("data", [])
    except Exception as e:
        print("JSearch error:", e)
        return []
    jobs = []
    for j in raw:
        jobs.append(normalize_job({
            "source": "jsearch",
            "title": j.get("job_title"),
            "company": j.get("employer_name"),
            "location": j.get("job_city") or j.get("job_country") or "",
            "description": j.get("job_description") or "",
            "salary_min": j.get("job_min_salary"),
            "salary_max": j.get("job_max_salary"),
            "apply_url": j.get("job_apply_link") or j.get("job_google_link"),
            "work_mode_hint": j.get("job_is_remote"),
            "job_type_hint": j.get("job_employment_type"),
        }))
    return jobs

import httpx

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"

async def fetch_remotive(q: str, limit: int = 30) -> list[dict]:
    params = {"search": q or "", "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(REMOTIVE_URL, params=params)
        r.raise_for_status()
        jobs = r.json().get("jobs", []) or []
        out = []
        for j in jobs:
            out.append({
                "title": j.get("title",""),
                "company": j.get("company_name",""),
                "location": j.get("candidate_required_location","Remote"),
                "apply_url": j.get("url",""),
                "source": "remotive",
                "work_mode": "remote",
            })
        return out
    except Exception as e:
        print("Remotive error:", e)
        return []


# ---------------------------
# Aggregate with multi-query fan-out
# ---------------------------
def _expand_queries(q: str) -> List[str]:
    q = (q or "").strip()
    # Add common synonyms to increase recall; tweak as needed
    if "react" in q.lower():
        return [q, "frontend developer", "react developer", "javascript developer"]
    if "data" in q.lower():
        return [q, "data analyst", "data scientist", "business intelligence"]
    if "python" in q.lower():
        return [q, "python developer", "backend developer", "software engineer"]
    return [q, "software developer", "software engineer"]

# feature flags (tweak as you like)
ENABLE_JOOBLE = True   # 403/Cloudflare in your region — keep off for now
ENABLE_ROZEE = True
ENABLE_MUSTAKBIL = True
ENABLE_ADZUNA = True
ENABLE_JSEARCH = True
ENABLE_SERPAPI = True   # uses the new fetch_serpapi_jobs()

PROVIDERS = [
    ("jooble",    fetch_jooble,               ENABLE_JOOBLE),
    ("jsearch",   fetch_jsearch,              ENABLE_JSEARCH),
    ("adzuna",    fetch_adzuna,               ENABLE_ADZUNA),
    ("serpapi",   fetch_serpapi_google_jobs,         ENABLE_SERPAPI),   # <-- name change
    ("rozee",     fetch_rozee,                ENABLE_ROZEE),
    ("mustakbil", fetch_mustakbil,            ENABLE_MUSTAKBIL),
]

async def aggregate_jobs(query: str, location: str) -> List[Dict]:
    queries = _expand_queries(query)
    tasks = []
    for q in queries:
        tasks += [
            fetch_jsearch(q, location),
            fetch_serpapi_google_jobs(q, location),
            fetch_adzuna(q, location),
            # temporarily disable the rest while we stabilize:
            fetch_jooble(q, location),
            fetch_remotive(q),
            fetch_rozee(q, location),
            fetch_mustakbil(q, location),
        ]

    results = await asyncio.gather(*tasks, return_exceptions=False)

# how many results per query slice
    per = len(results) // max(1, len(queries))

    for i, q in enumerate(queries):
        offset = i * per
        slice_ = results[offset: offset + per]
        lens = list(map(len, slice_))
    # keep the order exactly as in tasks above
        print(
            f"[{q}] → "
            f"JSearch:{lens[0]}  SerpAPI:{lens[1]}  Adzuna:{lens[2]}  "
            f"Jooble:{lens[3]}  Rozee:{lens[4]}  Mustakbil:{lens[5]}  Remotive:{lens[6]}"
        )

    all_jobs = [j for sub in results for j in sub]
    return dedupe_jobs(all_jobs)

    
