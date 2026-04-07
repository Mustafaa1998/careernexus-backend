# app/recommend.py
from __future__ import annotations
from typing import List, Dict, Any, Iterable
from collections import Counter, defaultdict
import httpx
from .config import settings

# --- 🔧 Try transformer-based recommendations first (if available) ---
try:
    import torch
    from sentence_transformers import util
    from app.career_model import model, career_titles, career_embeddings
    _TORCH_OK = True
except Exception as e:
    torch = None
    util = None
    model = None
    career_titles = []
    career_embeddings = None
    _TORCH_OK = False
    _TORCH_ERR = e

# --- 🧭 Heuristic (rule-based) fallback mapping ---
# Feel free to extend this list; keys are case-insensitive
DEFAULT_SKILL_MAP: Dict[str, List[str]] = {
    # 🐍 Programming Languages
    "python": [
        "Data Analyst", "Machine Learning Engineer", "AI Researcher",
        "Automation Engineer", "Backend Developer", "Data Scientist"
    ],
    "java": [
        "Backend Developer", "Android Developer", "Software Engineer",
        "Systems Architect", "Spring Boot Developer"
    ],
    "c++": [
        "Game Developer", "Embedded Systems Engineer", "Software Engineer",
        "High-Performance Computing Specialist"
    ],
    "c#": [
        "Unity Game Developer", "Desktop Application Developer", "Full Stack .NET Developer"
    ],
    "javascript": [
        "Frontend Developer", "React Developer", "Full Stack Engineer",
        "Node.js Developer", "Web Developer"
    ],
    "typescript": [
        "Frontend Developer", "Angular Developer", "React Developer", "Full Stack Engineer"
    ],
    "go": [
        "DevOps Engineer", "Cloud Infrastructure Engineer", "Backend Developer"
    ],
    "php": [
        "Web Developer", "Laravel Developer", "Backend Developer"
    ],
    "swift": [
        "iOS Developer", "Mobile App Engineer"
    ],
    "kotlin": [
        "Android Developer", "Mobile App Engineer"
    ],
    "r": [
        "Data Scientist", "Statistician", "Bioinformatics Researcher"
    ],

    # 💾 Databases / Data Tools
    "sql": ["Database Administrator", "Data Engineer", "Data Analyst"],
    "mysql": ["Database Administrator", "Data Engineer"],
    "postgresql": ["Data Engineer", "Backend Developer", "Database Architect"],
    "mongodb": ["Full Stack Developer", "Data Engineer", "Backend Developer"],
    "excel": ["Data Analyst", "Business Analyst", "Operations Executive"],
    "powerbi": ["Data Analyst", "Business Intelligence Developer"],
    "tableau": ["Data Visualization Specialist", "Data Analyst"],

    # ☁️ Cloud & DevOps
    "aws": ["Cloud Engineer", "DevOps Engineer", "Solutions Architect"],
    "azure": ["Cloud Engineer", "DevOps Engineer", "ML Engineer"],
    "gcp": ["Cloud Engineer", "Data Engineer", "AI Engineer"],
    "docker": ["DevOps Engineer", "Software Engineer", "Cloud Architect"],
    "kubernetes": ["DevOps Engineer", "Site Reliability Engineer"],
    "jenkins": ["DevOps Engineer", "Automation Engineer"],
    "git": ["Software Engineer", "DevOps Engineer", "Version Control Specialist"],
    "linux": ["System Administrator", "DevOps Engineer", "Cloud Engineer"],

    # 🤖 Machine Learning / AI
    "machine learning": [
        "Machine Learning Engineer", "AI Engineer", "Data Scientist", "Research Scientist"
    ],
    "deep learning": ["AI Engineer", "Data Scientist", "Research Scientist"],
    "nlp": ["NLP Engineer", "AI Researcher", "Data Scientist"],
    "computer vision": ["Computer Vision Engineer", "AI Engineer", "Research Scientist"],
    "tensorflow": ["Machine Learning Engineer", "AI Engineer"],
    "pytorch": ["AI Engineer", "Deep Learning Engineer"],
    "huggingface": ["NLP Engineer", "AI Engineer"],

    # 🧠 Data & Analytics
    "data analysis": ["Data Analyst", "Business Analyst", "Financial Analyst"],
    "data visualization": ["BI Analyst", "Data Analyst", "Visualization Specialist"],
    "statistics": ["Statistician", "Data Scientist", "Research Analyst"],
    "pandas": ["Data Analyst", "Machine Learning Engineer"],
    "numpy": ["Data Scientist", "Machine Learning Engineer"],

    # 🔒 Cybersecurity
    "cybersecurity": ["Cybersecurity Analyst", "Security Engineer", "Network Security Specialist"],
    "ethical hacking": ["Penetration Tester", "Cybersecurity Analyst"],
    "network security": ["Network Engineer", "Security Operations Analyst"],
    "firewalls": ["Security Engineer", "Network Administrator"],
    "encryption": ["Security Researcher", "Cryptography Engineer"],

    # 🕸️ Web / Frameworks
    "react": ["Frontend Developer", "React Developer", "UI Engineer"],
    "nextjs": ["Full Stack Developer", "Frontend Developer"],
    "angular": ["Frontend Developer", "UI Engineer"],
    "vue": ["Frontend Developer", "UI Developer"],
    "node": ["Backend Developer", "Full Stack Developer"],
    "express": ["Backend Developer", "API Engineer"],
    "django": ["Backend Developer", "Full Stack Developer"],
    "flask": ["Backend Developer", "Python Developer"],
    "laravel": ["Backend Developer", "PHP Developer"],
    "fastapi": ["Backend Developer", "API Engineer"],

    # 📱 Mobile
    "android": ["Android Developer", "Mobile Application Engineer"],
    "ios": ["iOS Developer", "Mobile Application Engineer"],
    "flutter": ["Cross-Platform Mobile Developer", "Mobile Engineer"],
    "react native": ["Mobile Developer", "React Native Engineer"],

    # 🎨 Design / Creativity
    "creativity": ["UI/UX Designer", "Graphic Designer", "Game Designer"],
    "adobe photoshop": ["Graphic Designer", "Visual Content Creator"],
    "illustrator": ["Graphic Designer", "Brand Designer"],
    "figma": ["UI/UX Designer", "Product Designer"],
    "canva": ["Content Creator", "Social Media Designer"],

    # 🧩 Soft Skills
    "communication": ["Project Manager", "Business Analyst", "Product Owner", "Sales Executive"],
    "leadership": ["Team Lead", "Operations Manager", "Scrum Master", "Project Manager"],
    "teamwork": ["HR Specialist", "Business Analyst", "Coordinator"],
    "problem solving": ["Software Engineer", "Systems Architect", "DevOps Engineer", "Consultant"],
    "analytical thinking": ["Data Analyst", "Consultant", "Researcher"],
    "adaptability": ["Customer Success Manager", "Operations Specialist"],

    # 🧑‍💼 Business / Management
    "project management": ["Project Manager", "Scrum Master", "Program Manager"],
    "agile": ["Scrum Master", "Agile Coach", "Product Manager"],
    "jira": ["Project Manager", "Product Manager"],
    "business": ["Business Analyst", "Marketing Manager", "Entrepreneur"],
    "marketing": ["Digital Marketing Specialist", "Content Strategist", "SEO Analyst"],
    "seo": ["SEO Specialist", "Content Strategist"],
    "finance": ["Financial Analyst", "Investment Advisor", "Accountant"],

    # 🧬 Research & Academia
    "research": ["Data Scientist", "Academic Researcher", "R&D Analyst"],
    "writing": ["Technical Writer", "Content Strategist", "Research Associate"],

    # ⚙️ General Engineering
    "engineering": ["Software Engineer", "Systems Engineer", "Data Engineer"],
    "architecture": ["Systems Architect", "Solution Architect"],
    "testing": ["QA Engineer", "Automation Tester", "Software Tester"],

    # 💬 Communication & Education
    "teaching": ["Lecturer", "Trainer", "Instructional Designer"],
    "public speaking": ["Corporate Trainer", "Sales Executive", "Marketing Lead"],

    # 🌐 Misc / Others
    "html": ["Frontend Developer", "Web Developer"],
    "css": ["Frontend Developer", "UI Developer"],
    "bootstrap": ["Frontend Developer", "UI Developer"],
    "tailwind": ["Frontend Developer", "UI Developer"],
    "rest": ["Backend Developer", "API Engineer"],
    "graphql": ["API Engineer", "Full Stack Developer"],
    "excel": ["Data Analyst", "Operations Executive"],
    "nosql": ["Data Engineer", "Backend Developer"],
}
    

# Simple aliases so “node”, “react”, “typescript”, etc. contribute to JavaScript,
# and common DB names contribute to SQL.
ALIASES: Dict[str, str] = {
    "js": "javascript",
    "node": "javascript",
    "node.js": "javascript",
    "react": "javascript",
    "typescript": "javascript",
    "ts": "javascript",
    "frontend": "javascript",

    "mysql": "sql",
    "postgres": "sql",
    "postgresql": "sql",
    "sqlite": "sql",
    "mssql": "sql",

    "ml": "python",
    "pytorch": "python",
    "tensorflow": "python",
    "pandas": "python",
    "numpy": "python",

    "rest": "problem solving",
    "api": "problem solving",
    "java": "problem solving",
    "oop": "problem solving",
}

def _normalize(s: str) -> str:
    return " ".join((s or "").split())

def _safe_list(x: Any) -> List[str]:
    if isinstance(x, list):
        return [str(v) for v in x]
    if isinstance(x, str):
        # allow comma/newline separated strings to be treated as list
        parts = [p.strip() for p in x.replace("\r", "").split("\n")]
        if len(parts) <= 1:
            parts = [p.strip() for p in x.split(",")]
        return [p for p in parts if p]
    return []

def _lower_tokens(items: Iterable[str]) -> List[str]:
    out = []
    for it in items:
        t = str(it).strip().lower()
        if not t:
            continue
        out.append(t)
    return out

def _build_user_text(profile: Dict[str, Any]) -> str:
    """Flatten relevant fields into one text string for embedding."""
    parts: List[str] = []
    parts.append(profile.get("name", "") or "")
    resume = profile.get("resume") or {}
    skills = resume.get("skills") or []
    education = resume.get("education") or []
    experience = resume.get("experience") or ""
    summary = resume.get("summary") or ""
    projects = resume.get("projects") or []

    # ensure strings
    parts.extend([str(s) for s in skills])
    parts.extend([str(e) for e in education])
    parts.extend([str(p) for p in projects])
    parts.append(str(experience))
    if summary:
        parts.append(str(summary))

    psych = profile.get("psychometric_result") or profile.get("psychometric") or {}
    scores = psych.get("scores") or {}
    if scores:
        parts.extend([f"{k}: {v}" for k, v in scores.items()])
    if psych.get("personality_type"):
        parts.append(f"personality: {psych['personality_type']}")

    return _normalize(" ".join(p for p in parts if p))

# -------- Heuristic recommender (used when Torch/embeddings are unavailable) --------
def _heuristic_recommend(profile: Dict[str, Any], top_k: int = 3) -> List[str]:
    resume = profile.get("resume") or {}

    # collect skill-ish tokens
    skills = _safe_list(resume.get("skills"))
    projects = _safe_list(resume.get("projects"))
    education = _safe_list(resume.get("education"))
    exp = str(resume.get("experience") or "")
    summary = str(resume.get("summary") or "")

    # make one big lowercase text blob for contains checks
    text_blob = " \n ".join(
        _safe_list(skills) + _safe_list(projects) + _safe_list(education) + [exp, summary]
    ).lower()

    # normalize skills list to lowercase tokens (also split comma/newline strings)
    skill_tokens = set(_lower_tokens(skills))

    # expand “aliases” based on raw text/skills
    for alias, base in ALIASES.items():
        if alias in text_blob:
            skill_tokens.add(base)

    # also add direct words found in text that match mapping keys
    for key in DEFAULT_SKILL_MAP.keys():
        if key in text_blob:
            skill_tokens.add(key)

    # No signals? Try simple domain inference from education/summary keywords
    if not skill_tokens:
        generic = ["Software Engineer", "Full Stack Engineer", "Data Analyst", "Project Manager"]
        return generic[:top_k]

    # Score careers from matched keys
    scores: Counter[str] = Counter()
    for key in skill_tokens:
        careers = DEFAULT_SKILL_MAP.get(key, [])
        if not careers:
            continue
        # weight: higher if the exact token came from “skills” (vs generic text match)
        w = 3 if key in _lower_tokens(skills) else 1
        for c in careers:
            scores[c] += w

    if not scores:
        generic = ["Software Engineer", "Full Stack Engineer", "Data Analyst", "Project Manager"]
        return generic[:top_k]

    # sort by score desc, then title asc for stability
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [title for title, _ in ranked[:top_k]]

# -------- Public API --------
def recommend_from_profile(profile: Dict[str, Any], top_k: int = 3) -> List[str]:
    """
    Generate top-k career recommendations (titles only) from a unified profile dict.
    Uses transformer embeddings if available; otherwise uses the heuristic mapping above.
    """
    # Transformer path
    if _TORCH_OK and model and career_titles and career_embeddings is not None:
        text = _build_user_text(profile)
        if not text:
            return []
        with torch.no_grad():
            user_vec = model.encode(text, convert_to_tensor=True)
            sims = util.cos_sim(user_vec, career_embeddings)[0]
            k = min(top_k, len(career_titles))
            topk = torch.topk(sims, k=k)
            indices = topk.indices.tolist()
        return [career_titles[i] for i in indices]

    # Heuristic fallback (replaces “Career A/B/C”)
    recs = _heuristic_recommend(profile, top_k=top_k)
    if recs:
        return recs
    # ultra-fallback (shouldn’t hit often)
    return ["Software Engineer", "Full Stack Engineer", "Data Analyst"][:top_k]

# app/recommend.py (add at bottom, keep your existing code)

async def fetch_job_recommendations_from_profile(profile: dict, limit: int = 10):
    """
    Call the Job Recommendation microservice and return job list.
    `profile` should contain skills, degree, domain, etc.
    """
    base = settings.JOB_REC_BASE.rstrip("/")

    # ---- Build payload for your job service ----
    payload = {
        # adjust these keys to match your job-backend API contract
        "skills": profile.get("skills", []),
        "target_title": profile.get("target_title") or profile.get("current_title"),
        "location": profile.get("location") or "Karachi",
        "limit": limit,
        # Add more fields if your job API expects them
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        # 👉 replace "/recommend/jobs_live" if your job backend uses a different path
        resp = await client.post(f"{base}/recommend/jobs_live", json=payload)
        resp.raise_for_status()
        return resp.json()


async def fetch_university_recommendations_from_profile(profile: dict, limit: int = 10):
    """
    Call the University Recommendation microservice and return university list.
    """
    base = settings.UNI_REC_BASE.rstrip("/")

    payload = {
        # Adjust these keys to match your uni-backend API
        "program": profile.get("target_program") or profile.get("degree_program"),
        "level": profile.get("degree_level") or "bs",
        "city": profile.get("preferred_city") or "",
        "limit": limit,
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        # 👉 replace "/recommend/universities" with your exact endpoint
        resp = await client.post(f"{base}/recommend/universities", json=payload)
        resp.raise_for_status()
        return resp.json()
