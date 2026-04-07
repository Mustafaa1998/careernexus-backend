import re
import pandas as pd
from typing import List, Dict, Any
from difflib import SequenceMatcher
from .loader import _canon_field, _univ_key_from_name

def _norm(s: str) -> str:
    return str(s or "").strip().lower()

def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()

# -------- Program canonicalization (local, lightweight) --------
# If you already have _canon_program in loader.py, you can import and use it instead.
PROGRAM_CANON_MAP: Dict[str, str] = {
    # CS/IT family
    "cs": "computer science", "computer science": "computer science", "computing": "computer science",
    "se": "software engineering", "software": "software engineering", "software engineering": "software engineering",
    "it": "information technology", "information technology": "information technology",
    "ai": "artificial intelligence", "artificial intelligence": "artificial intelligence",
    "ds": "data science", "data science": "data science",

    # Engineering branches
    "me": "mechanical engineering", "mechanical": "mechanical engineering", "mechanical engineering": "mechanical engineering",
    "ee": "electrical engineering", "electrical": "electrical engineering", "electrical engineering": "electrical engineering",
    "ce": "civil engineering", "civil": "civil engineering", "civil engineering": "civil engineering",
    "che": "chemical engineering", "chemical": "chemical engineering", "chemical engineering": "chemical engineering",
    "mechatronics": "mechatronics engineering", "mechatronics engineering": "mechatronics engineering",
    "industrial": "industrial engineering", "industrial engineering": "industrial engineering",
    "aero": "aerospace engineering", "aerospace": "aerospace engineering", "aerospace engineering": "aerospace engineering",
    "biomedical": "biomedical engineering", "biomedical engineering": "biomedical engineering",
    "petroleum": "petroleum engineering", "petroleum engineering": "petroleum engineering",
    "materials": "materials engineering", "materials engineering": "materials engineering",
    "telecom": "telecommunications engineering", "telecommunication": "telecommunications engineering",
    "environmental": "environmental engineering", "environmental engineering": "environmental engineering",
    "computer engineering": "computer engineering",
}

def _program_synonyms(canon: str) -> list[str]:
    canon = (canon or "").strip().lower()
    mapping = {
        # ---- CS/IT ----
        "software engineering": ["software engineering", "se", "soft eng"],
        "computer science": ["computer science", "cs", "computing"],
        "artificial intelligence": ["artificial intelligence", "ai"],
        "data science": ["data science", "ds", "data analytics"],
        "information technology": ["information technology", "it", "csit"],
        "computer engineering": ["computer engineering"],

        # ---- Engineering ----
        "mechanical engineering": ["mechanical engineering", "mechanical", "me", "mech"],
        "electrical engineering": ["electrical engineering", "electrical", "ee", "power", "electronics"],
        "civil engineering": ["civil engineering", "civil", "ce"],
        "chemical engineering": ["chemical engineering", "chemical", "chem eng", "che"],
        "mechatronics engineering": ["mechatronics engineering", "mechatronics"],
        "industrial engineering": ["industrial engineering", "industrial"],
        "aerospace engineering": ["aerospace engineering", "aero", "aerospace"],
        "biomedical engineering": ["biomedical engineering", "biomedical"],
        "petroleum engineering": ["petroleum engineering", "petroleum"],
        "materials engineering": ["materials engineering", "materials"],
        "telecommunications engineering": ["telecommunications engineering", "telecom"],
        "environmental engineering": ["environmental engineering", "environmental"],

        # ---- Business ----
        "business administration": [
            "business administration", "bba", "b.b.a", "mba",
            "business", "management", "commerce", "business mgmt"
        ],
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
    return mapping.get(canon, [canon] if canon else [])

def _blob(df):
    return (
        df.get("program_name", "").astype(str) + " " +
        df.get("programs_offered", "").astype(str) + " " +
        df.get("specialization", "").astype(str) + " " +
        df.get("field", "").astype(str)
    ).str.lower()

def _canon_program(x: str) -> str:
    x = _norm(x)
    if not x:
        return ""
    # exact map first
    if x in PROGRAM_CANON_MAP:
        return PROGRAM_CANON_MAP[x]
    # strip common prefixes like "bs ", "ms ", etc.
    x2 = re.sub(r"^(bs|be|bsc|ms|msc|mphil|phd)\s+", "", x)
    return PROGRAM_CANON_MAP.get(x2, x2)

# -------- Synonyms per canonical program (for fuzzy matching) --------
PROGRAM_SYNONYMS = {
    # IT/CS
    "software engineering": {"software engineering", "se", "software", "soft eng"},
    "computer science": {"computer science", "cs", "computing", "bscs", "bs cs"},
    "artificial intelligence": {"artificial intelligence", "ai"},
    "data science": {"data science", "ds", "data analytics"},
    "information technology": {"information technology", "it", "csit"},

    # Engineering
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

    # Business
    "business administration": {"business administration", "bba", "b.b.a", "mba", "business", "management", "commerce", "business mgmt"},
    "finance": {"finance", "banking", "accounting & finance", "bs finance", "financial"},
    "accounting": {"accounting", "accountancy", "bs accounting"},
    "economics": {"economics", "economic", "bs economics"},
    "marketing": {"marketing", "sales", "brand management"},
    "human resource management": {"human resource management", "hrm", "hr", "people management"},
    "supply chain management": {"supply chain management", "supply chain", "scm"},
}


# Default orders used when ONLY a field is provided (no program_name)
PROGRAM_ORDER_BY_FIELD: Dict[str, list[str]] = {
    "computer_science": [
        "software engineering",
        "computer science",
        "artificial intelligence",
        "data science",
        "information technology",
        "computer engineering",
    ],
    "engineering": [
        "mechanical engineering",
        "electrical engineering",
        "civil engineering",
        "chemical engineering",
        "computer engineering",
        "mechatronics engineering",
        "industrial engineering",
        "telecommunications engineering",
        "environmental engineering",
        "biomedical engineering",
        "materials engineering",
        "aerospace engineering",
        "petroleum engineering",
    ],
    "business": [
        "business administration",
        "finance",
        "accounting",
        "economics",
        "marketing",
        "human resource management",
        "supply chain management",
    ],
    "medical": [
        "medicine",
        "dentistry",
        "pharmacy",
        "nursing",
        "physiotherapy",
        "biotechnology",
        "biochemistry",
    ],
    "social_science": [
        "psychology",
        "education",
        "sociology",
        "political science",
        "international relations",
        "mass communication",
    ],
}

def _matches_program(pname: str, program_norm: str, blob: str) -> bool:
    """
    Safer fuzzy program matching:
      1) canonical equality (best)
      2) synonym word-boundary match in program_norm or blob
      3) fuzzy ratio >= 0.80 (a bit stricter)
      4) if query is very short (<=3 chars), DO NOT do naive substring across blob
    """
    q = _norm(pname)
    if not q:
        return True

    canon_q = _canon_program(q)
    if canon_q and program_norm == canon_q:
        return True

    syns = PROGRAM_SYNONYMS.get(canon_q, {q})
    # word-boundary check for each synonym
    for s in syns:
        s_esc = re.escape(s)
        if re.search(rf"\b{s_esc}\b", program_norm):
            return True
        if re.search(rf"\b{s_esc}\b", blob):
            return True

    # fuzzy similarity on normalized titles
    if _similar(q, program_norm) >= 0.80:
        return True

    # very short tokens like "ee", "me", "ir" can create lots of false matches
    # so we *avoid* naive substring for queries <= 3 chars
    if len(q) <= 3:
        return False

    # last resort: raw substring (safe for longer phrases)
    return q in blob


def recommend(
    df_unis: pd.DataFrame,
    df_prog: pd.DataFrame,
    level: str,
    field: str,
    city: str,
    max_fee: float | None,
    limit,  # ✅ allow None/0/unlimited
    program_name: str = "",
):
    if df_prog is None or len(df_prog) == 0:
        return []

    # ✅ LIMIT handling: None or 0 => unlimited
    try:
        limit_n = None if limit is None else int(limit)
        if limit_n is not None and limit_n <= 0:
            limit_n = None
    except Exception:
        limit_n = None

    # ---------- small helpers ----------
    def _series(df: pd.DataFrame, *cands: str) -> pd.Series:
        """Return df[col].astype(str) for the first existing col in cands; else empty series."""
        for c in cands:
            if c in df.columns:
                return df[c].astype(str)
        return pd.Series([""] * len(df), index=df.index, dtype="string")

    def _int_or_none(x):
        try:
            s = ("" if x is None else str(x)).replace(",", "").strip()
            return int(s) if s.isdigit() else None
        except Exception:
            return None

    # ---------- Build uni lookup ----------
    uni_dict: Dict[str, Dict[str, Any]] = {}
    if df_unis is not None and len(df_unis) > 0:
        for _, u in df_unis.iterrows():
            key = _univ_key_from_name(u.get("university_name", ""))
            if not key:
                continue
            uni_dict[key] = {
                "university_name": u.get("university_name", ""),
                "city": u.get("city", ""),
                "province": u.get("province", ""),
                "type": u.get("type", ""),
                "ranking": u.get("ranking_tier", u.get("ranking", "")),
                "website_url": u.get("website_url", u.get("website", "")),
                "apply_url": u.get("apply_url", ""),
            }

    df = df_prog.copy()

    # ---------- normalized columns ----------
    if "program_norm" not in df.columns:
        df["program_norm"] = _series(df, "program_name").apply(_canon_program)

    if "field_norm" not in df.columns:
        # canon from field_category (fallback to field)
        df["field_norm"] = _series(df, "field_category", "field").apply(_canon_field)

    if "level_norm" not in df.columns:
        # infer from degree_level + program_name
        def _infer_level(x: str) -> str:
            x = _norm(x)
            if re.search(r"\b(phd|doctoral|doctorate)\b", x): return "phd"
            if re.search(r"\b(ms|m\.?sc|mphil|master)\b", x): return "ms"
            if re.search(r"\b(bs|b\.?sc|be|bachelor)\b", x): return "bs"
            return ""
        df["level_norm"] = (
            _series(df, "degree_level") + " " + _series(df, "program_name")
        ).apply(_infer_level)

    # ✅ ALWAYS remove PhD rows (system rule)
    df = df[~df["level_norm"].astype(str).str.contains(r"\bphd\b", na=False)]

    # ---------- robust text blob for fuzzy/search ----------
    # Prefer field_category over field
    blob_series = (
        _series(df, "program_name") + " " +
        _series(df, "field_category", "field") + " " +
        _series(df, "specialization") + " " +
        _series(df, "programs_offered")
    ).str.lower()

    # ---------- Field filter ----------
    fcanon = _canon_field(field)

    # ✅✅ ONLY CHANGE: FORCE CS ONLY
    # ✅ Field must be provided (no default CS)
    if not field or not str(field).strip():
        return []

    # ✅ Only CS/IT family allowed
    if fcanon != "computer_science":
        return []

    # ✅ PhD not allowed (BS/MS only)
    lcanon = _norm(level)
    if lcanon and re.search(r"\b(phd|doctoral|doctorate)\b", lcanon):
        return []


    if fcanon:
        df = df[df["field_norm"] == fcanon]
        blob_series = blob_series.loc[df.index]  # ✅ keep aligned

    # ---------- Program filter (STRICT first, then synonyms) ----------
    pname = _norm(program_name)
    if pname:
        qcanon_main = _canon_program(pname)

        # If the program name is short, ensure an exact match first
        if len(pname) <= 3:
            df_strict = df[df["program_norm"] == qcanon_main]
        else:
            # Use your _matches_program function with more robust matching
            df_strict = df[df.apply(lambda r: _matches_program(
                pname,
                r.get("program_norm", ""),
                " ".join([
                    _norm(r.get("program_name", "")),
                    _norm(r.get("programs_offered", "")),
                    _norm(r.get("specialization", "")),
                    _norm(r.get("field_category", r.get("field", ""))),
                ])
            ), axis=1)]

        if not df_strict.empty:
            df = df_strict
            blob_series = blob_series.loc[df.index]  # ✅ keep aligned
        else:
            # Fallback to synonym matching if no strict match
            qcanon = _canon_program(pname or "")
            if qcanon:
                syns = _program_synonyms(qcanon)
                blob_now = blob_series.loc[df.index]  # ✅ aligned blob

                parts = []
                for s in syns:
                    s = (s or "").strip().lower()
                    if not s:
                        continue
                    parts.append(rf"\b{re.escape(s)}\b" if " " not in s else re.escape(s))

                if parts:
                    pat = r"(?:%s)" % "|".join(parts)
                    mask = blob_now.str.contains(pat, na=False)
                    df = df.loc[mask].reset_index(drop=True)

                    # ✅ rebuild blob_series aligned to new df
                    blob_series = (
                        _series(df, "program_name") + " " +
                        _series(df, "field_category", "field") + " " +
                        _series(df, "specialization") + " " +
                        _series(df, "programs_offered")
                    ).str.lower()

    # ✅ IMPORTANT FIX: Level/City/Fee filters should apply ALWAYS (not only when pname provided)

    # ---------- Level filter ----------
    lcanon = _norm(level)
    if lcanon:
        if lcanon in ("bs", "be", "bsc", "bachelors", "bachelor"):
            df = df[df["level_norm"].isin(["bs", "be", ""])]
        else:
            df = df[df["level_norm"].str.contains(lcanon, na=False)]

    # ---------- City filter ----------
    ccanon = _norm(city)
    if ccanon:
        prog_city = _series(df, "city").str.lower().str.strip()
        exact_prog = df[prog_city == ccanon]
        if not exact_prog.empty:
            df = exact_prog

    # ---------- Fee filter ----------
    if max_fee is not None:
        # Apply the filter to semester_fee if available, otherwise use fee_per_year
        fee_series = _series(df, "semester_fee", "fee_per_year").map(_int_or_none)
        df = df.loc[(fee_series.notna()) & (fee_series <= int(max_fee))]

    if df.empty:
        return []

    # ---------- dedupe & sort ----------
    # Use degree_level (not level), since DB column is degree_level
    # (if some columns are missing in some dataset, pandas will still handle)
    subset_cols = [c for c in ["university_name", "program_name", "degree_level", "city"] if c in df.columns]
    if subset_cols:
        df = df.drop_duplicates(subset=subset_cols, keep="first")

    df = df.sort_values(by=[c for c in ["university_name", "program_name"] if c in df.columns]).reset_index(drop=True)

    # Friendly ordering when only field is given
    if not pname:
        order = PROGRAM_ORDER_BY_FIELD.get(fcanon, [])
        if order and "program_norm" in df.columns:
            df = df.assign(
                _order=df["program_norm"].apply(lambda p: order.index(p) if p in order else 999)
            ).sort_values(by=["_order", "university_name"], ascending=[True, True])

    # ---------- Build response ----------
    items: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        uname = r.get("university_name", "")
        ukey = _univ_key_from_name(uname)
        u = uni_dict.get(ukey, {})

        # city fallback with uni
        if ccanon:
            prog_city = _norm(r.get("city", ""))
            uni_city = _norm(u.get("city", ""))
            if prog_city and prog_city != ccanon and uni_city != ccanon:
                continue
            if (not prog_city) and uni_city and uni_city != ccanon:
                continue

        items.append({
            "university_name": u.get("university_name", uname),
            "program_name": r.get("program_name", "") or r.get("programs_offered", ""),
            "level": r.get("degree_level", "") or r.get("level_norm", ""),
            "field": r.get("field_category", "") or r.get("field_norm", ""),
            "city": u.get("city", r.get("city", "")),
            "province": u.get("province", r.get("province", "")),
            "annual_fee": r.get("fee_per_year", r.get("annual_fee", "")),
            "semester_fee": r.get("semester_fee", ""),
            "ranking": u.get("ranking", r.get("ranking", "")),
            "website_url": u.get("website_url", r.get("website_url", "")),
            "apply_url": r.get("apply_url", u.get("apply_url", "")),
        })

        # ✅ limit applies only if limit_n is set; otherwise unlimited
        if limit_n is not None and len(items) >= limit_n:
            break

    return items
