# recommend/rank_jobs.py
import re

def _contains(blob: str, skill: str) -> bool:
    s = (skill or "").strip().lower()
    if not s:
        return False
    # word-boundary for single tokens; substring for phrases
    if " " in s:
        return s in blob
    return re.search(r"\b" + re.escape(s) + r"\b", blob) is not None

def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0

def rank_jobs(user, jobs, limit=20):
    # use only user-provided skills
    u_skills = [s.lower().strip() for s in user.get("skills", []) if s]
    u_set = set(u_skills)
    exp = max(0, int(user.get("experience_months", 0)))
    prefs = user.get("prefs", {})
    pref_mode = prefs.get("work_mode", "any")
    pref_type = prefs.get("job_type", "any")
    pref_locs = [x.lower() for x in prefs.get("preferred_locations", [])]

    ranked = []
    for j in jobs:
        title = (j.get("title") or "")
        desc  = (j.get("description") or "")
        loc   = (j.get("location") or "")
        job_mode = j.get("work_mode", "onsite")
        job_type = j.get("job_type", "full_time")

        # filter by user prefs
        if pref_mode != "any" and job_mode != pref_mode:
            continue
        if pref_type != "any" and job_type != pref_type:
            continue

        blob = f"{title} {desc}".lower()

        # skill match: fraction of user skills found in text
        hits = [s for s in u_skills if _contains(blob, s)]
        s_skills = len(set(hits)) / max(1, len(u_set))

        # exp alignment: favor junior roles for <= 12 months, else neutral
        is_junior = any(k in title.lower() for k in ["intern", "junior", "graduate", "trainee"])
        s_exp = 1.0 if (exp <= 12 and is_junior) else (0.7 if exp <= 12 else 0.9)

        # location proximity: soft boost if preferred location appears
        s_loc = 1.0 if any(x in loc.lower() for x in pref_locs) else 0.6 if pref_locs else 0.8

        score = 0.55*s_skills + 0.25*s_exp + 0.20*s_loc

        ranked.append({
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "location": loc,
            "work_mode": job_mode,
            "job_type": job_type,
            "salary": j.get("salary", ""),
            "match": round(score, 3),
            "apply_url": j.get("apply_url", ""),
            "source": j.get("source", "")
        })

    return sorted(ranked, key=lambda x: x["match"], reverse=True)[:limit]
