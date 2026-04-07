# app/routes/chat.py
from typing import Dict, Any, List
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.external_service import (
    get_profile_full_me,
    recommend_jobs_live,
    recommend_jobs_from_profile,
    recommend_jobs_from_resume,
    recommend_universities,
)
from app.services.llm_service import chat_llm
from app.services.memory_service import save_message, get_history, save_profile_snapshot

router = APIRouter(prefix="/chat", tags=["Chat"])
security = HTTPBearer()


class ChatRequest(BaseModel):
    message: str


PROGRAM_SYNONYMS = {
    "software engineering": {"software engineering", "se", "software", "soft eng"},
    "computer science": {"computer science", "cs", "computing", "bscs", "bs cs"},
    "artificial intelligence": {"artificial intelligence", "ai"},
    "data science": {"data science", "ds", "data analytics"},
    "information technology": {"information technology", "it", "csit"},

    "electrical engineering": {"electrical engineering", "electrical", "ee", "power", "electronics"},
    "mechanical engineering": {"mechanical engineering", "mechanical", "me", "mech"},
    "civil engineering": {"civil engineering", "civil", "ce"},
    "chemical engineering": {"chemical engineering", "chemical", "chem eng", "che"},
    "mechatronics engineering": {"mechatronics engineering", "mechatronics"},
    "industrial engineering": {"industrial engineering", "industrial"},
    "aerospace engineering": {"aerospace engineering", "aerospace", "aero"},
    "biomedical engineering": {"biomedical engineering", "biomedical"},
    "petroleum engineering": {"petroleum engineering", "petroleum"},
    "materials engineering": {"materials engineering", "materials"},
    "telecommunications engineering": {"telecommunications engineering", "telecom", "telecommunication"},
    "environmental engineering": {"environmental engineering", "environmental"},

    "business administration": {"business administration", "bba", "b.b.a", "mba", "business", "management", "commerce", "business mgmt"},
    "finance": {"finance", "banking", "accounting & finance", "bs finance", "financial"},
    "accounting": {"accounting", "accountancy", "bs accounting"},
    "economics": {"economics", "economic", "bs economics"},
    "marketing": {"marketing", "sales", "brand management"},
    "human resource management": {"human resource management", "hrm", "hr", "people management"},
    "supply chain management": {"supply chain management", "supply chain", "scm"},
}

KNOWN_CITIES = [
    "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "multan", "peshawar",
    "quetta", "hyderabad", "sialkot", "gujranwala", "sukkur", "abbottabad", "bahawalpur",
    "dera ismail khan", "d.i. khan", "gilgit", "skardu", "mansehra", "mardan", "swat",
    "jamshoro", "taxila", "wah cantt", "topi", "khuzdar", "sargodha", "sheikhupura",
    "kasur", "larkana", "mirpurkhas", "nawabshah", "rahim yar khan",
]

PROVINCES = {
    "sindh": "Sindh",
    "punjab": "Punjab",
    "khyber pakhtunkhwa": "Khyber Pakhtunkhwa",
    "kp": "Khyber Pakhtunkhwa",
    "kpk": "Khyber Pakhtunkhwa",
    "balochistan": "Balochistan",
    "baluchistan": "Balochistan",
    "gilgit baltistan": "Gilgit Baltistan",
    "gb": "Gilgit Baltistan",
}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def looks_like_uni_request(text: str) -> bool:
    t = _clean(text)
    triggers = ["university", "universities", "uni", "admission", "degree", "campus", "recommend", "suggest", "ms", "bs", "bba", "mba"]
    return any(w in t for w in triggers)


def extract_level(text: str) -> str:
    t = _clean(text)
    if re.search(r"\bphd\b|\bdoctorate\b", t):
        return "phd"
    if re.search(r"\bms\b|\bm\.s\b|\bmasters\b|\bmaster\b|\bmsc\b|\bmba\b", t):
        return "ms"
    if re.search(r"\bbs\b|\bb\.s\b|\bbachelors\b|\bbachelor\b|\bundergrad\b|\bbba\b", t):
        return "bs"
    return ""


def extract_city(text: str) -> str:
    t = _clean(text)
    for c in KNOWN_CITIES:
        if c in t:
            if c == "d.i. khan":
                return "D.I. Khan"
            return "Karachi" if c == "karachi" else c.title()
    return ""


def extract_province(text: str) -> str:
    t = _clean(text)
    for k, v in PROVINCES.items():
        if re.search(rf"\b{re.escape(k)}\b", t):
            return v
    return ""


def extract_program(text: str) -> str:
    t = _clean(text)

    for canonical, syns in PROGRAM_SYNONYMS.items():
        for s in syns:
            if re.search(rf"\b{re.escape(_clean(s))}\b", t):
                return canonical

    m = re.search(r"\b(ms|bs|bachelors|masters)\s+([a-z& ]{2,60})\b", t)
    if m:
        candidate = _clean(m.group(2))
        candidate = re.sub(r"\b(universit(y|ies)|program|degree|admission|in|near|within|under|below)\b.*$", "", candidate).strip()
        short_map = {"se": "software engineering", "cs": "computer science", "ai": "artificial intelligence"}
        return short_map.get(candidate, candidate)

    if re.search(r"\bbba\b", t) or re.search(r"\bmba\b", t):
        return "business administration"

    return ""


def extract_budget(text: str) -> dict:
    t = _clean(text)
    mode = "semester" if ("semester" in t or "per semester" in t) else "annual"

    m = re.search(r"\b(under|below|less than|<=)\s*(\d{2,7})\s*(k)?\b", t)
    if m:
        num = int(m.group(2))
        if m.group(3):
            num *= 1000
        return {"amount": num, "mode": mode}

    m2 = re.search(r"\b(under|below|less than|<=)?\s*(\d{1,3})\s*(lac|lakh|lacs)\b", t)
    if m2:
        num = int(m2.group(2)) * 100000
        return {"amount": num, "mode": mode}

    m3 = re.search(r"\bbudget\s*(\d{2,7})\s*(k)?\b", t)
    if m3:
        num = int(m3.group(1))
        if m3.group(2):
            num *= 1000
        return {"amount": num, "mode": mode}

    return {}


@router.post("")
async def chat_endpoint(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    creds: HTTPAuthorizationCredentials = Depends(security),
):
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    token = creds.credentials

    # 1) Load profile bundle
    try:
        profile_bundle = await get_profile_full_me(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Unable to fetch profile: {str(e)}")

    profile = profile_bundle.get("profile", {}) or {}
    resume = profile.get("resume", {}) or {}
    psycho = profile_bundle.get("psychometric_result", {}) or {}
    careers = profile_bundle.get("recommended_careers", []) or []

    user_id = (profile.get("email") or profile_bundle.get("email") or "").strip().lower()
    if not user_id:
        # fallback stable id from token prefix (avoid "unknown-session" collision)
        user_id = f"session-{token[:12]}"

    # 2) Save snapshot + user message
    await save_profile_snapshot(db=db, session_id=user_id, profile_data=profile_bundle)
    await save_message(db=db, session_id=user_id, role="user", content=message)

    # 3) ✅ IMPORTANT: history for LLM should NOT include profile_snapshot JSON
    history = await get_history(db, session_id=user_id, limit=20)
    clean_history = [h for h in history if h.role in ("user", "assistant")]  # filter
    clean_history = clean_history[-12:]
    history_text = "\n".join([f"{h.role}: {h.content}" for h in clean_history])

    # 4) Compact context (no raw full JSON)
    context_str = f"""
USER PROFILE:
Name: {profile.get("name")}
Email: {profile.get("email")}
Education: {resume.get("education", [])}
Skills: {resume.get("skills", [])}
Projects: {resume.get("projects", [])}

PSYCHOMETRIC:
{psycho}

RECOMMENDED CAREERS:
{careers}

CHAT HISTORY:
{history_text}
""".strip()

    msg_lower = message.lower()

    # CAREER
    career_triggers = ["career", "careers", "recommended career", "which career", "career path"]
    if any(t in msg_lower for t in career_triggers):
        if careers:
            reply = "Based on your profile + resume, these careers suit you best:\n\n"
            for c in careers:
                reply += f"• **{c}**\n"
            reply += (
                "\n\n**Mentor plan (next 2 weeks):**\n"
                "1) Pick 1 target role from the list.\n"
                "2) Improve 2 core skills for that role.\n"
                "3) Build 1 strong project and upload on GitHub.\n"
                "Tell me which role you like most, I’ll make a step-by-step roadmap."
            )
        else:
            reply = "I can’t see computed career recommendations right now, but I can still mentor you from your resume. Tell me: Dev, Data, or AI?"

        await save_message(db=db, session_id=user_id, role="assistant", content=reply)
        return {"reply": reply, "intent": "career", "jobs": None, "universities": None}

    # JOBS
    job_triggers = ["job", "jobs", "apply", "vacancy", "internship", "hiring", "opening", "openings"]
    if any(t in msg_lower for t in job_triggers):

        def _items(resp: Any) -> List[Dict[str, Any]]:
            if resp is None:
                return []
            if isinstance(resp, list):
                return resp
            if isinstance(resp, dict):
                return resp.get("items") or resp.get("jobs") or []
            return []

        use_resume = ("resume" in msg_lower) or ("from resume" in msg_lower)
        use_profile = ("profile" in msg_lower) or ("from profile" in msg_lower) or ("my profile" in msg_lower)

        try:
            if use_resume:
                jobs_response = await recommend_jobs_from_resume(token)
                intent = "jobs_from_resume"
            elif use_profile:
                jobs_response = await recommend_jobs_from_profile(token)
                intent = "jobs_from_profile"
            else:
                job_payload = {
                    "query": message,
                    "skills": [],
                    "work_mode": "any",
                    "job_type": "any",
                    "preferred_locations": ["Pakistan"],
                    "city": "Pakistan",
                    "salary_min": 0,
                    "experience_months": 0,
                    "limit": 20,
                }
                jobs_response = await recommend_jobs_live(job_payload)
                intent = "jobs_live"

            jobs_items = _items(jobs_response)
            reply = "✅ Job matches loaded. See the cards below 👇" if jobs_items else (
                "I couldn’t find strong matches right now — but don’t worry 🙂\n\n"
                "Tell me one thing and I’ll try again:\n"
                "• what role you want (e.g., backend / frontend / data)\n"
                "OR\n"
                "• one key skill (e.g., python / react / finance)\n"
            )
            reply += "\n\n🔎 For more openings and advanced filters, please visit the **Job Recommender** section."

            await save_message(db=db, session_id=user_id, role="assistant", content=reply)
            return {"reply": reply, "intent": intent, "jobs": jobs_response, "universities": None}

        except Exception as e:
            reply = await chat_llm(
                user_message=message,
                context=context_str + f"\n\n[Job API error: {str(e)}]\n",
            )
            reply += "\n\n🔎 For more openings and advanced filters, please visit the **Job Recommender** section."

            await save_message(db=db, session_id=user_id, role="assistant", content=reply)
            return {"reply": reply, "intent": "job_llm_fallback", "jobs": None, "universities": None}

    # UNIVERSITIES
    if looks_like_uni_request(message):
        try:
            level = extract_level(message)
            program_name = extract_program(message)
            city = extract_city(message)
            province = extract_province(message)

            budget_info = extract_budget(message)
            budget_amount = budget_info.get("amount")
            budget_mode = budget_info.get("mode", "annual")

            missing = []
            if not level:
                missing.append("level (BS/MS)")
            if not program_name:
                missing.append("program (e.g., AI, CS, BBA, Electrical Engineering)")

            if missing:
                reply = (
                    "I can recommend universities, but I need:\n"
                    f"• {', '.join(missing)}\n\n"
                    "Example: **Recommend MS AI universities in Karachi under 200k**"
                )
                await save_message(db=db, session_id=user_id, role="assistant", content=reply)
                return {"reply": reply, "intent": "university_need_more", "jobs": None, "universities": None}

            uni_payload = {
                "level": level,
                "field": "",
                "city": city or "",
                "program_name": program_name,
                "limit": 30,
                "page": 1,
                "page_size": 30,
                "province": province or "",
            }

            if budget_amount and budget_mode == "semester":
                uni_payload["max_fee"] = int(budget_amount)

            universities = await recommend_universities(uni_payload)

            # post filter if needed
            if isinstance(universities, dict) and budget_amount:
                items = universities.get("items", []) or []
                filtered = []
                for it in items:
                    try:
                        annual_fee = it.get("annual_fee")
                        semester_fee = it.get("semester_fee")
                        fee_val = semester_fee if budget_mode == "semester" else annual_fee
                        if fee_val is None or int(fee_val) <= int(budget_amount):
                            filtered.append(it)
                    except Exception:
                        filtered.append(it)
                universities["items"] = filtered
                universities["total"] = len(filtered)

            reply_lines = [
                "Here are universities that match what you asked:",
                f"• Level: **{level.upper()}**",
                f"• Program: **{program_name.title()}**",
            ]
            if city:
                reply_lines.append(f"• City: **{city}**")
            if province:
                reply_lines.append(f"• Province: **{province}**")
            if budget_amount:
                reply_lines.append(f"• Budget limit: **{budget_amount:,} PKR** ({'per semester' if budget_mode=='semester' else 'per year'})")

            reply_lines.append(
                "\n**Mentor tip:** shortlist by (1) fee, (2) ranking, (3) location, (4) alumni/job outcomes.\n"
                "If you tell me **public vs private** and your **exact budget**, I’ll rank best 3 for you."
            )

            reply = "\n".join(reply_lines)
            reply += "\n\n🔎 For complete details, comparisons, and filters, please check the **University Recommender** module."

            await save_message(db=db, session_id=user_id, role="assistant", content=reply)
            return {"reply": reply, "intent": "university", "jobs": None, "universities": universities}

        except Exception as e:
            reply = await chat_llm(
                user_message=message,
                context=context_str + f"\n\n[University API error: {str(e)}]\n",
            )
            reply += "\n\n🔎 For complete details, comparisons, and filters, please check the **University Recommender** module."

            await save_message(db=db, session_id=user_id, role="assistant", content=reply)
            return {"reply": reply, "intent": "university_fallback_llm", "jobs": None, "universities": None}

    # GENERAL CHAT
    reply = await chat_llm(user_message=message, context=context_str)
    await save_message(db=db, session_id=user_id, role="assistant", content=reply)
    return {"reply": reply, "intent": "general", "jobs": None, "universities": None}
