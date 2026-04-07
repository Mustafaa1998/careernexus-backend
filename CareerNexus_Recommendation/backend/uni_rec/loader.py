# loader.py — clean, canonical version

from pathlib import Path
import pandas as pd
import re

# DB bits
from .database import engine, SessionLocal
from .models import University, Program
from sqlalchemy import or_, func
from .models import Program, University
USE_DB = True  # set True to load from PostgreSQL instead of CSV

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CSV_UNIS = "pakistan_fest_universities.csv"
CSV_PROG = "pakistan_fest_programs.csv"


# ----------------------------- helpers -----------------------------

from pathlib import Path
import pandas as pd

from pathlib import Path
import pandas as pd

def _read_csv_robust(p: Path) -> pd.DataFrame:
    """
    Try several encodings so Windows CSVs won't crash with UnicodeDecodeError.
    """
    for enc in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
        try:
            df = pd.read_csv(p, encoding=enc)
            print(f"📄 Loaded {p.name} with encoding={enc}, rows={len(df)}")
            return df
        except Exception:
            continue
    # last attempt – let pandas raise the real error
    return pd.read_csv(p)


def _norm(s: str) -> str:
    return str(s or "").strip().lower()


# Canonical field mappings / synonyms
FIELD_ALIASES = {
    "computer_science": [
        "computer science", "cs", "bscs", "bs cs", "bs(cs)", "computing",
        "software engineering", "se", "csit", "it", "information technology"
    ],
    "business": ["business", "bba", "mba", "commerce", "finance", "accounting", "marketing"],
    "engineering": ["engineering", "electrical", "mechanical", "civil", "mechatronics", "industrial"],
    "social_science": ["psychology", "sociology", "education", "international relations", "ir", "mass communication"],
    "medical": ["medicine", "mbbs", "dental", "dentistry", "nursing", "physiotherapy", "pharmacy"],
}

def _canon_field(q: str) -> str:
    qn = (q or "").strip().lower()
    if not qn:
        return ""
    # short codes
    if qn in {"cs", "se", "it", "csit"}:
        return "computer_science"
    if qn in {"ee", "ce"}:
        return "engineering"
    if qn in {"bba", "mba"}:
        return "business"

    # keywords → families
    if any(k in qn for k in ["business", "commerce", "management"]):
        return "business"
    if any(k in qn for k in ["engineer", "electrical", "mechanical", "civil", "mechatronics", "industrial"]):
        return "engineering"
    if any(k in qn for k in ["computer", "software", "artificial intelligence", "data science", "it", "computing"]):
        return "computer_science"
    if any(k in qn for k in ["psychology", "sociology", "education", "international relations", "mass communication"]):
        return "social_science"
    if any(k in qn for k in ["mbbs", "medicine", "dental", "dentistry", "nursing", "physio", "pharmacy"]):
        return "medical"
    return qn

def _univ_key_from_name(name: str) -> str:
    """
    Build a robust key from university_name only.
    Lowercase, remove punctuation, collapse spaces, and strip common aliases.
    This guarantees the same key across both CSVs even if IDs differ.
    """
    s = str(name or "").lower().strip()
    # unify common aliases
    s = s.replace("national university of computer & emerging sciences", "fast")
    s = s.replace("fast-nuces", "fast")
    s = s.replace("nuces", "fast")
    s = s.replace("ned university of engineering and technology", "ned")
    s = s.replace("institute of business administration", "iba")
    s = s.replace("&", "and")
    # remove non-alphanumeric
    s = re.sub(r"[^a-z0-9\s]", "", s)
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _canon_program(q: str) -> str:
    qn = _norm(q)
    if not qn:
        return ""

    mapping = {
        # ---- IT / CS ----
        "software engineering": ["software engineering", "se", "soft eng"],
        "computer science": ["computer science", "cs", "computing", "bs cs", "bscs"],
        "artificial intelligence": ["artificial intelligence", "ai"],
        "data science": ["data science", "ds", "data analytics"],
        "information technology": ["information technology", "it", "csit"],

        # ---- Engineering ----
        "electrical engineering": ["electrical engineering", "electrical", "ee", "power", "electronics"],
        "mechanical engineering": ["mechanical engineering", "mechanical", "me", "mech"],
        "civil engineering": ["civil engineering", "civil", "ce"],
        "chemical engineering": ["chemical engineering", "chem eng", "che", "chemical"],
        "mechatronics engineering": ["mechatronics engineering", "mechatronics"],
        "industrial engineering": ["industrial engineering", "industrial"],
        "aerospace engineering": ["aerospace engineering", "aerospace", "aero"],
        "biomedical engineering": ["biomedical engineering", "biomedical"],
        "petroleum engineering": ["petroleum engineering", "petroleum"],
        "materials engineering": ["materials engineering", "materials"],
        "telecommunications engineering": ["telecommunications engineering", "telecom", "telecommunication"],
        "environmental engineering": ["environmental engineering", "environmental"],

        # ---- Business ----
        "business administration": ["business administration", "bba", "b.b.a", "mba", "business", "management", "commerce", "business mgmt"],
        "finance": ["finance", "banking", "accounting & finance", "bs finance", "financial"],
        "accounting": ["accounting", "accountancy", "bs accounting"],
        "economics": ["economics", "economic", "bs economics"],
        "marketing": ["marketing", "sales", "brand management"],
        "human resource management": ["human resource management", "hrm", "hr", "people management"],
        "supply chain management": ["supply chain management", "supply chain", "scm"],

        # ---- Medical ----
        "medicine": ["medicine", "mbbs", "md", "medical"],
        "dentistry": ["dentistry", "bds", "dental"],
        "pharmacy": ["pharmacy", "pharm d", "pharm-d"],
        "nursing": ["nursing"],
        "physiotherapy": ["physiotherapy", "dpt", "physical therapy"],
        "biotechnology": ["biotechnology", "biotech"],
        "biochemistry": ["biochemistry"],

        # ---- Social Sciences ----
        "psychology": ["psychology", "psych"],
        "education": ["education", "b.ed", "bed", "m.ed", "med"],
        "sociology": ["sociology", "socio"],
        "political science": ["political science", "politics"],
        "international relations": ["international relations", "ir"],
        "mass communication": ["mass communication", "journalism", "media studies"],
    }

    for canon, keys in mapping.items():
        for k in keys:
            if qn == _norm(k):
                return canon
    return qn



def _canon_level(x: str, program_name: str = "") -> str:
    s = (x or "") + " " + (program_name or "")
    s = s.lower()

    # ---- Doctoral
    if re.search(r"\b(phd|doctoral|doctorate)\b", s): return "phd"

    # ---- Masters (incl. MBA/MSc/MS/MPhil)
    if re.search(r"\b(mba|ms|m\.?sc|msc|mphil|master)\b", s): return "ms"

    # ---- Bachelors (BS/BE/BSc/BA/BBA and 5-year professional bachelors)
    if re.search(r"\b(bs|be|b\.?sc|bsc|ba|bba|b\.?ed|bed)\b", s): return "bs"
    if re.search(r"\b(mbbs|bds|pharm(\s*d|-d)|dpt|bpt)\b", s): return "bs"  # professional bachelors

    return ""


# --------- inference helpers (TOP-LEVEL; used inside load_programs) ---------

def infer_field(row: pd.Series) -> str:
    txt = " ".join([
        str(row.get("program_name", "")),
        str(row.get("field", "")),
        str(row.get("specialization", "")),
        str(row.get("programs_offered", "")),
    ]).lower()

    # CS family
    if re.search(r"\b(cs|computer\s*science|software\s*engineering|se|it|information\s*technology|computing)\b", txt):
        return "computer_science"
    # business family
    if re.search(r"\b(bba|mba|business|commerce|finance|accounting|marketing)\b", txt):
        return "business"
    # engineering (generic / branches)
    if re.search(r"\b(engineering|electrical|mechanical|civil|mechatronics|industrial)\b", txt):
        return "engineering"
    # social sciences
    if re.search(r"\b(psychology|sociology|education|ir|international\s*relations|mass\s*communication)\b", txt):
        return "social_science"
    # medical
    if re.search(r"\b(medicine|mbbs|dental|dentistry|nursing|physio|pharmacy)\b", txt):
        return "medical"
    return ""


def infer_level(row: pd.Series) -> str:
    txt = " ".join([
        str(row.get("level", "")),
        str(row.get("program_name", "")),
        str(row.get("programs_offered", "")),
        str(row.get("specialization", "")),
    ]).lower()
    if re.search(r"\b(phd|doctoral|doctorate)\b", txt):
        return "phd"
    if re.search(r"\b(ms|m\.?sc|msc|mphil|master)\b", txt):
        return "ms"
    # Treat BE as BS-equivalent for undergrad; include BBA/MBBS/DPT/etc.
    if re.search(r"\b(bs|b\.?sc|bsc|be|ba|bba|b\.?ed|bed|mbbs|bds|dpt|pharm(\s*d|-d))\b", txt):
        return "bs"
    return ""


def infer_program(row: pd.Series) -> str:
    parts = [
        str(row.get("program_name", "")),
        str(row.get("programs_offered", "")),
        str(row.get("specialization", "")),
        str(row.get("field", "")),
    ]
    txt = " ".join(parts).lower()

    # ---------- CS/IT ----------
    if re.search(r"\bsoftware\s*engineering\b|\bse\b|\bsoft\s*eng\b", txt):
        return "software engineering"
    if re.search(r"\bcomputer\s*science\b|\bcs\b|\bcomputing\b", txt):
        return "computer science"
    if re.search(r"\bartificial\s*intelligence\b|\bai\b", txt):
        return "artificial intelligence"
    if re.search(r"\bdata\s*science\b|\bds\b|\bdata\s*analytics\b", txt):
        return "data science"
    if re.search(r"\binformation\s*technology\b|\bit\b|\bcsit\b", txt):
        return "information technology"
    if re.search(r"\bcomputer\s*engineering\b", txt):
        return "computer engineering"

    # ---------- Engineering ----------
    if re.search(r"\bmechanical(\s*engineering)?\b|\bmech\b|\bme\b", txt):
        return "mechanical engineering"
    if re.search(r"\belectrical(\s*engineering)?\b|\bee\b|\bpower\b|\belectronics\b", txt):
        return "electrical engineering"
    if re.search(r"\bcivil(\s*engineering)?\b|\bce\b", txt):
        return "civil engineering"
    if re.search(r"\bchemical(\s*engineering)?\b|\bchem\s*eng\b|\bche\b", txt):
        return "chemical engineering"
    if re.search(r"\bmechatronics(\s*engineering)?\b", txt):
        return "mechatronics engineering"
    if re.search(r"\bindustrial(\s*engineering)?\b", txt):
        return "industrial engineering"
    if re.search(r"\baerospace(\s*engineering)?\b|\baero\b", txt):
        return "aerospace engineering"
    if re.search(r"\bbiomedical(\s*engineering)?\b", txt):
        return "biomedical engineering"
    if re.search(r"\bpetroleum(\s*engineering)?\b", txt):
        return "petroleum engineering"
    if re.search(r"\bmaterials(\s*engineering)?\b", txt):
        return "materials engineering"
    if re.search(r"\btele(communication|com)\b", txt):
        return "telecommunications engineering"
    if re.search(r"\benvironmental(\s*engineering)?\b", txt):
        return "environmental engineering"

    # ---------- Business ----------
    if re.search(r"\b(bba|mba|business\s*administration|business\s*management)\b", txt):
        return "business administration"
    if re.search(r"\bfinance\b|\bbanking\b", txt):
        return "finance"
    if re.search(r"\baccount(ing|ancy)\b", txt):
        return "accounting"
    if re.search(r"\beconomics?\b", txt):
        return "economics"
    if re.search(r"\bmarketing\b", txt):
        return "marketing"
    if re.search(r"\bhuman\s*resource(s)?\b|\bhrm\b|\bhr\b", txt):
        return "human resource management"
    if re.search(r"\bsupply\s*chain(\s*management)?\b|\bscm\b", txt):
        return "supply chain management"

    # ---------- Medical ----------
    if re.search(r"\bmedicine\b|\bmbbs\b|\bmd\b|\bmedical\b", txt):
        return "medicine"
    if re.search(r"\bdentistry\b|\bbds\b|\bdental\b", txt):
        return "dentistry"
    if re.search(r"\bpharmacy\b|\bpharm(\s*d|-d)\b", txt):
        return "pharmacy"
    if re.search(r"\bnursing\b", txt):
        return "nursing"
    if re.search(r"\bphysio(therapy)?\b|\bdpt\b|\bphysical\s*therapy\b", txt):
        return "physiotherapy"
    if re.search(r"\bbiotechnolog(y|ies)\b|\bbiotech\b", txt):
        return "biotechnology"
    if re.search(r"\bbiochemistry\b", txt):
        return "biochemistry"

    # ---------- Social Sciences ----------
    if re.search(r"\bpsychology\b|\bpsych\b", txt):
        return "psychology"
    if re.search(r"\beducation\b|\bb\.?ed\b|\bm\.?ed\b", txt):
        return "education"
    if re.search(r"\bsociology\b|\bsocio\b", txt):
        return "sociology"
    if re.search(r"\bpolitical\s*science\b|\bpolitics\b", txt):
        return "political science"
    if re.search(r"\binternational\s*relations\b|\bir\b", txt):
        return "international relations"
    if re.search(r"\bmass\s*communication\b|\bjournalism\b", txt):
        return "mass communication"

    return ""


# ----------------------------- loaders -----------------------------

def load_universities() -> pd.DataFrame:
    if USE_DB:
        with SessionLocal() as s:
            rows = s.query(University).all()
            data = []
            for u in rows:
                data.append({
                    "id":               u.id,
                    "university_name":  u.university_name or "",
                    "province":         u.province or "",
                    "city":             u.city or "",
                    "type":             u.type or "",
                    "website":          (u.website or "").strip(),
                    "apply_url":        (u.apply_url or "").strip(),
                    "ranking_tier":     (u.ranking_tier or "").strip(),
                    "univ_key":         (u.univ_key or "").strip(),
                    "website_url":      (u.website or "").strip(),  # alias used by API
                })
            df = pd.DataFrame(data).fillna("")
            print(f"✅ Loaded {len(df)} universities from DB")
            return df

    # CSV fallback (unchanged from your previous version)
    from pathlib import Path
    DATA_DIR = Path(__file__).parent / "data"
    CSV_UNIS = DATA_DIR / "pakistan_fest_universities.csv"
    if not CSV_UNIS.exists():
        print(f"⚠️ {CSV_UNIS} missing — returning empty DF.")
        return pd.DataFrame()
    df = pd.read_csv(CSV_UNIS, encoding="utf-8").fillna("")
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype(str).str.strip()
    if "website_url" not in df.columns:
        df["website_url"] = df.get("website", "")
    print(f"✅ Loaded {len(df)} universities from {CSV_UNIS.name}")
    return df



def load_programs() -> pd.DataFrame:
    if USE_DB:
        sql = """
        SELECT
            p.id,
            p.university_fk,
            u.university_name,
            u.province,
            u.city,
            u.ranking_tier,
            u.website AS website_url,
            COALESCE(p.apply_url, u.apply_url) AS apply_url,
            p.program_name,
            p.degree_level,
            p.field_category,
            p.duration_years,
            p.eligibility,
            p.fee_per_year,
            p.semester_fee,
            p.required_traits
        FROM programs p
        JOIN universities u ON u.id = p.university_fk
        """
        df = pd.read_sql(sql, engine).fillna("")
        # Normalize types (important for filters/scoring)
        if "duration_years" in df.columns:
            df["duration_years"] = pd.to_numeric(df["duration_years"], errors="coerce").astype("Int64")
        if "fee_per_year" in df.columns:
            df["fee_per_year"] = pd.to_numeric(df["fee_per_year"], errors="coerce").astype("Int64")
        if "semester_fee" in df.columns:
            df["semester_fee"] = pd.to_numeric(df["semester_fee"], errors="coerce").astype("Int64")  # Ensure it's an integer
        print(f"✅ Loaded {len(df)} programs from DB (joined)")
        return df

    # CSV fallback (unchanged structure)
    from pathlib import Path
    DATA_DIR = Path(__file__).parent / "data"
    CSV_PROGS = DATA_DIR / "pakistan_fest_programs.csv"
    if not CSV_PROGS.exists():
        print(f"⚠️ {CSV_PROGS} missing — returning empty DF.")
        return pd.DataFrame()
    df = pd.read_csv(CSV_PROGS, encoding="utf-8").fillna("")
    for c in df.select_dtypes(include=["object", "string"]).columns:
        df[c] = df[c].astype(str).str.strip()
    print(f"✅ Loaded {len(df)} programs from {CSV_PROGS.name}")
    return df

# --- Autocomplete helpers ---
# loader.py  (add near the bottom)

from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import University, Program

def suggest_programs_db(
    q: str = "",                # field or keyword (e.g., "cs", "ai", "engineering")
    city: str = "",
    level: str = "",
    max_fee: float | None = None,
    limit: int = 10,            # how many programs to return (0/None => ALL)
    universities_limit: int = 6,# how many unis per program
    page: int = 1,              # pagination: which page of programs
    page_size: int | None = None
):
    # Canonicalize field/level
    q_norm = _canon_field(q)
    city_norm = (city or "").strip().lower()
    level_norm = (level or "").strip().lower()

    # ✅✅ ONLY CHANGE: FORCE CS ONLY
    # ✅ Field required (no default CS)
    if not q or not str(q).strip():
        return {"items": [], "page": page, "next_page": None, "total_count": 0}

    # ✅ Only CS/IT family allowed
    if q_norm != "computer_science":
        return {"items": [], "page": page, "next_page": None, "total_count": 0}

    # ✅ PhD not allowed (BS/MS only)
    if level_norm and re.search(r"\b(phd|doctoral|doctorate)\b", level_norm):
        return {"items": [], "page": page, "next_page": None, "total_count": 0}
        
    # ✅ interpret limit=0/None as "unlimited" (paging fix)
    try:
        limit_int = 0 if limit is None else int(limit)
    except Exception:
        limit_int = 0

    # ✅ default page_size = limit if not provided
    if page_size is None:
        page_size = limit_int

    # normalize page
    try:
        page = max(1, int(page))
    except Exception:
        page = 1

    # open session
    session: Session = SessionLocal()

    try:
        # Base query joining programs to universities
        base = (
            session.query(
                func.trim(
                    func.regexp_replace(
                        func.lower(Program.program_norm),
                        r'^(bs|be|bsc)\s+',
                        '',
                        'g'
                    )
                ).label("program_key"),
                Program.program_name,
                Program.level_norm,
                Program.field_norm,
                Program.university_fk,
                University.university_name,
                University.city,
                University.province,
                University.ranking_tier.label("ranking"),
                University.website.label("website_url"),
                Program.apply_url,
                Program.semester_fee,
            )
            .join(University, University.id == Program.university_fk)
        )

        # ✅ HARD BLOCK: NEVER show PhD (even if level is empty or data is messy)
        base = base.filter(Program.level_norm != "phd")
        base = base.filter(~func.lower(Program.program_name).contains("phd"))

        # Field filter (broad)
        if q_norm:
            base = base.filter(Program.field_norm == q_norm)
            '''parts = {q_norm} | set(FIELD_ALIASES.get(q_norm, []))
            parts_l = [p.lower() for p in parts if p]

            like_parts = [f"%{p.lower()}%" for p in parts if p]

            base = base.filter(
                or_(
                    Program.field_norm == q_norm,
                    func.lower(Program.field_category).in_(parts_l),
            # allow program_name to match any alias via ILIKE
                   # or_(*[Program.program_name.ilike(lp) for lp in like_parts])
                ) 
            )'''


        # Level filter
        if level_norm:
            if level_norm in ("bs", "be", "bsc", "bachelors", "bachelor"):
                base = base.filter(Program.level_norm.in_(["bs", "be", ""]))
            else:
                base = base.filter(Program.level_norm.contains(level_norm))

        # ✅ Max Fee filter (0 is valid too)
        if max_fee is not None:
            try:
                mf = float(max_fee)
                base = base.filter(
                    or_(
                        Program.semester_fee <= mf,  # Apply the filter to semester_fee
                        Program.fee_per_year <= mf   # Fallback to fee_per_year (annual fee)
                    )
                )
            except Exception:
                pass


        # City filter (program city OR university city)
        # City filter (program city OR university city)
        if city_norm:
            # compare lowercased equality; if you prefer partials, use ilike(f"%{city_norm}%")
            base = base.filter(func.lower(University.city) == city_norm)

        rows = base.all()
        if not rows:
            return {"items": [], "page": page, "next_page": None, "total_count": 0}

        # Group by program_key
        from collections import defaultdict
        grouped = defaultdict(list)
        for r in rows:
            key = (r.program_key or "").strip().lower()
            if key:
                grouped[key].append(r)

        # Sort programs: most universities offering it first; tie-breaker: name
        programs_sorted = sorted(
            grouped.items(),
            key=lambda kv: (-len({x.university_fk for x in kv[1]}), kv[0])
        )

        total_count = len(programs_sorted)

        # ✅ Pagination on programs (FIX: page_size/limit=0 => show ALL)
        try:
            ps = int(page_size) if page_size is not None else 0
        except Exception:
            ps = 0

        if ps <= 0:
            page = 1
            start = 0
            end = total_count
            next_page = None
        else:
            ps = max(1, ps)
            start = (page - 1) * ps
            end = start + ps
            next_page = page + 1 if end < total_count else None

        page_slice = programs_sorted[start:end]

        results = []
        for prog_key, rows_for_prog in page_slice:
            # unique universities for this program
            seen = set()
            unis_full = []
            for r in rows_for_prog:
                if r.university_fk in seen:
                    continue
                seen.add(r.university_fk)
                unis_full.append({
                    "university_name": r.university_name,
                    "city": r.city,
                    "semester_fee": r.semester_fee or "",
                    "province": r.province,
                    "ranking": r.ranking or "",
                    "website_url": r.website_url or "",
                    "apply_url": r.apply_url or "",
                })

            # trim to requested count
            try:
                ul = max(1, int(universities_limit))
            except Exception:
                ul = 6
            unis_trim = unis_full[: ul]

            # pick a display name for the program (kept)
            display_name = rows_for_prog[0].program_name

            results.append({
                "program": prog_key,
                "universities_count": len(unis_full),
                "universities": unis_trim,
            })

        return {"items": results, "page": page, "next_page": next_page, "total_count": total_count}

    finally:
        session.close()

# loader.py
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import func, case, or_, and_
from .models import Program, University
from .schemas import RecommendRequest

# Small helpers (reuse your existing canonicalizers if present)
def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

_RANK_ORDER = {"A": 1, "B": 2, "C": 3}
_FEST_FIELDS = {
    "computer science", "software engineering", "data science",
    "artificial intelligence", "it", "information technology",
    "engineering", "electrical engineering", "mechanical engineering",
    "civil engineering", "mathematics", "physics", "chemistry"
}

def recommend_db(db, req: RecommendRequest) -> Dict[str, Any]:
    """
    Flat results with filters/sorting/pagination.
    Prefers program.city; falls back to university.city.
    """
    q = (
        db.query(Program, University)
        .join(University, Program.university_fk == University.id)
    )

    # --------- Filters ---------
    # level
    if req.level:
        lv = _norm(req.level)
        if lv in ("bs", "be", "bsc", "bachelors", "bachelor"):
            q = q.filter(Program.level_norm.in_(["bs", "be", ""]))
        else:
            q = q.filter(Program.level_norm.ilike(f"%{lv}%"))

    # field (use both field_norm and field_category)
    if req.field:
        fcanon = _norm(req.field)
        q = q.filter(
            or_(
                Program.field_norm == fcanon,
                func.lower(Program.field_category).ilike(f"%{fcanon}%")
            )
        )

    # program_name (match name/specialization/programs_offered)
    if req.program_name:
        pname = _norm(req.program_name)
        q = q.filter(
            or_(
                func.lower(Program.program_name).ilike(f"%{pname}%"),
                func.lower(Program.specialization).ilike(f"%{pname}%"),
                func.lower(Program.programs_offered).ilike(f"%{pname}%"),
            )
        )

    # city: prefer program.city, else university.city
    if req.city:
        c = _norm(req.city)
        q = q.filter(
            or_(
                func.lower(func.coalesce(Program.city, "")).ilike(c),
                func.and_(
                    func.coalesce(Program.city, "") == "",
                    func.lower(func.coalesce(University.city, "")) == c
                )
            )
        )

    # province
    if req.province:
        q = q.filter(func.lower(University.province) == _norm(req.province))

    # type (public/private)
    if req.type:
        q = q.filter(func.lower(University.type) == _norm(req.type))

    # max_fee
    if req.max_fee is not None:
        # Apply the filter to semester_fee if available
        q = q.filter(
            or_(
                Program.semester_fee <= int(req.max_fee),  # Filter by semester fee
                Program.fee_per_year <= int(req.max_fee)   # Fallback to annual fee (fee_per_year)
            )
        )

    # ranking by tier (A/B/C)
    if req.ranking_tier:
        rt = req.ranking_tier.strip().upper()
        q = q.filter(func.upper(University.ranking_tier) == rt)

    # offers_fest (derive from field_norm/category)
    if req.offers_fest is True:
        q = q.filter(
            or_(
                func.lower(Program.field_norm).in_(_FEST_FIELDS),
                func.lower(Program.field_category).in_(_FEST_FIELDS)
            )
        )

    # --------- Sorting ---------
    # ranking: A=1, B=2, C=3, unknown=99
    rank_num = case(
        (func.upper(University.ranking_tier) == "A", 1),
        (func.upper(University.ranking_tier) == "B", 2),
        (func.upper(University.ranking_tier) == "C", 3),
        else_=99,
    )

    if req.sort_by == "fee":
        sort_col = Program.fee_per_year
    elif req.sort_by == "semester_fee":
        sort_col = Program.semester_fee
    elif req.sort_by == "name":
        sort_col = University.university_name
    else:
        sort_col = rank_num

    if req.order == "desc":
        q = q.order_by(sort_col.desc(), University.university_name.asc())
    else:
        q = q.order_by(sort_col.asc(), University.university_name.asc())

    # --------- Pagination ---------
    page = max(1, int(req.page or 1))

    total = q.count()

    # ✅ If page_size is missing OR 0 => return ALL filtered rows
    if req.page_size is None or int(req.page_size) <= 0:
        page_size = total if total > 0 else 1
    else:
        page_size = max(1, int(req.page_size))

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows: List[Tuple[Program, University]] = q.all()

    items: List[Dict[str, Any]] = []
    for p, u in rows:
        # prefer program city; fallback to uni city
        city = p.city or u.city
        items.append({
            "university_name": u.university_name,
            "program_name": p.program_name or p.programs_offered or "",
            "level": p.level or p.level_norm or "",
            "field": p.field or p.field_norm or p.field_category or "",
            "city": city,
            "province": u.province,
            "annual_fee": p.fee_per_year,
            "semester_fee": p.semester_fee,
            "ranking_tier": u.ranking_tier,
            "website_url": u.website or u.website_url,
            "apply_url": p.apply_url or u.apply_url,
        })

    return {
        "intent": "recommendations",
        "page": page,
        "next_page": (page + 1) if (page * page_size) < total else None,
        "total": total,
        "items": items
    }
