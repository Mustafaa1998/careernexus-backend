# app.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Query
from .loader import suggest_programs_db
from .schemas import RecommendRequest
from .recommender import recommend
from .loader import load_universities, load_programs, _canon_field, _univ_key_from_name


app = FastAPI(title="CareerNexus – FEST University Recommender", version="0.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Pull from Postgres because loader.USE_DB = True
UNIS = load_universities()
PROGS = load_programs()


# --- add this to app.py below UNIS, PROGS ---
from fastapi import HTTPException

# ---- Adaptive limits helper ----
def _adaptive_limit(q: str, base: int, peak: int) -> int:
    """Short query => fewer results; longer/specific => more."""
    q = (q or "").strip()
    if not q:
        return base
    L = len(q)
    # crude but effective: scale from base → peak as query gets longer
    if L < 3:   return max(3, base // 2)
    if L < 6:   return base
    if L < 10:  return int((base + peak) / 2)
    return peak

@app.get("/health")
def health():
    return {"ok": True, "universities": len(UNIS), "programs": len(PROGS)}


@app.get("/v1/debug")
def debug_inspect(field: str = "", city: str = ""):
    import pandas as pd

    def uni_keys_from(df: pd.DataFrame) -> set[str]:
        if "univ_key" in df.columns:
            return set(df["univ_key"].astype(str).str.lower().str.strip().unique().tolist())
        if "university_name" in df.columns:
            return set(df["university_name"].astype(str).map(_univ_key_from_name))
        return set()

    uni_count = len(UNIS)
    prog_count = len(PROGS)

    sample_unis = UNIS.head(5).to_dict(orient="records")
    sample_progs = PROGS.head(5).to_dict(orient="records")

    # build comparable key sets safely
    unis_keys = uni_keys_from(UNIS)
    progs_keys = uni_keys_from(PROGS)

    inter = sorted(list(unis_keys & progs_keys))
    only_unis = sorted(list(unis_keys - progs_keys))[:10]
    only_progs = sorted(list(progs_keys - unis_keys))[:10]

    # safe field/city filter preview
    fcanon = _canon_field(field) if field else ""
    dfp = PROGS.copy()
    if fcanon and "field_norm" in dfp.columns:
        dfp = dfp[dfp["field_norm"] == fcanon]
    if city and "city_norm" in dfp.columns:
        dfp = dfp[dfp["city_norm"] == city.lower().strip()]

    return {
        "counts": {"universities": uni_count, "programs": prog_count},
        "preview_universities": sample_unis,
        "preview_programs": sample_progs,
        "keys": {
            "uni_keys_total": len(unis_keys),
            "prog_keys_total": len(progs_keys),
            "intersection_count": len(inter),
            "intersection_sample": inter[:20],
            "unis_only_sample": only_unis,
            "progs_only_sample": only_progs
        },
        "field_filter": {"requested": field, "canonical": fcanon, "programs_matching_field": int(len(dfp))},
        "sample_filtered_programs": dfp.head(8).to_dict(orient="records"),
    }


@app.get("/health")
def health():
    return {"ok": True, "universities": len(UNIS), "programs": len(PROGS)}

@app.post("/v1/recommend")
def v1_recommend(req: RecommendRequest):
    # ✅ Field required
    if not (req.field or "").strip():
        raise HTTPException(status_code=422, detail="Please enter a field.")

    # ✅ Only BS/MS allowed (PhD not allowed)
    lv = (req.level or "").strip().lower()
    if "phd" in lv or "doctoral" in lv or "doctorate" in lv:
        return {"intent": "university_recommendation", "total": 0, "items": []}

    items = recommend(
        df_unis=UNIS,
        df_prog=PROGS,
        level=req.level,
        field=req.field,
        city=req.city,
        max_fee=req.max_fee,
        limit=req.limit,
        program_name=req.program_name,
    )

    for item in items:
        item["semester_fee"] = item.get("semester_fee", "")

    return {"intent": "university_recommendation", "total": len(items), "items": items}


from collections import Counter

# app.py — REPLACE the entire /v1/suggest/programs route with this

from fastapi import HTTPException

@app.get("/v1/suggest/programs")
def suggest_programs(
    field: str = "",
    city: str = "",
    level: str = "",
    max_fee: float | None = None,
    limit: int = 10,
    with_universities: bool = True,
    universities_limit: int = 10,
    page: int = 1,
    page_size: int | None = None
):
    # ✅ REQUIRED: Field must be provided (no default CS)
    if not (field or "").strip():
        raise HTTPException(status_code=422, detail="Please enter a field.")

    # ✅ BS/MS only (no PhD)
    lv = (level or "").strip().lower()
    if "phd" in lv or "doctoral" in lv or "doctorate" in lv:
        return {
            "intent": "program_suggestions",
            "filters": {"field": field, "city": city, "level": level, "max_fee": max_fee},
            "page": 1,
            "next_page": None,
            "total": 0,
            "programs": [],
        }

    # ✅ normalize ints safely (query params can be strings)
    try:
        page_i = int(page)
    except Exception:
        page_i = 1
    page_i = max(1, page_i)

    try:
        limit_i = 0 if limit is None else int(limit)
    except Exception:
        limit_i = 0

    # ✅ paging rule:
    # - if page_size is provided: use it
    # - else: use limit
    # - if resulting page_size <= 0 => UNLIMITED (show all)
    if page_size is None:
        ps_i = limit_i
    else:
        try:
            ps_i = int(page_size)
        except Exception:
            ps_i = 0

    # ✅ when unlimited, force page=1 so UI doesn't get confusing
    if ps_i <= 0:
        page_i = 1

    data = suggest_programs_db(
        q=field or "",
        city=city,
        level=level,
        max_fee=max_fee,
        limit=limit_i,                    # pass normalized
        universities_limit=universities_limit,
        page=page_i,                      # pass normalized
        page_size=ps_i                    # pass normalized (0 => unlimited)
    )

    for item in data.get("items", []):
        item.pop("display_name", None)

    return {
        "intent": "program_suggestions",
        "filters": {"field": field, "city": city, "level": level, "max_fee": max_fee},
        "page": data.get("page"),
        "next_page": data.get("next_page"),
        "total": data.get("total_count", 0),
        "programs": data.get("items", []),
    }
