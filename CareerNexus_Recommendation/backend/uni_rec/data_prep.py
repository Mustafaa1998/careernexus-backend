"""
data_prep.py
Merges Wikipedia-detailed universities with your FEST programs CSV,
adds FEST/ranking/meta, and writes clean CSVs for the API.

Inputs (expected in uni_rec/data/):
- pakistan_fest_programs.csv          (your curated program-level data)
- hec_fest_universities.csv           (from hec_scraper.py)
Optional:
- pakistan_fest_universities.csv      (if you have a uni-level CSV with city/province)

Outputs:
- universities_clean.csv
- programs_clean.csv
"""

from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
F_PROGS = DATA_DIR / "pakistan_fest_programs.csv"
F_UNIS  = DATA_DIR / "pakistan_fest_universities.csv"   # optional
F_WIKI  = DATA_DIR / "hec_fest_universities.csv"        # from scraper
OUT_UNI = DATA_DIR / "universities_clean.csv"
OUT_PRO = DATA_DIR / "programs_clean.csv"

def _key(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("&", "and")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

# Canonicalizers (must match your loader/recommender logic)
def _canon_level(level: str, program_name: str = "") -> str:
    blob = f"{level} {program_name}".lower()
    if re.search(r"\b(phd|doctoral|doctorate)\b", blob): return "phd"
    if re.search(r"\b(ms|m\.?sc|master|mphil)\b", blob): return "ms"
    if re.search(r"\b(bs|b\.?sc|be|bachelor)\b", blob): return "bs"
    return ""

FIELD_ALIASES = {
    "computer_science": ["it","cs","ai","data science","software","computing","computer"],
    "engineering": ["engineering","civil","electrical","mechanical","mechatronics","chemical","industrial","telecom","materials","petroleum","biomedical","environmental"],
    "business": ["business","bba","mba","accounting","finance","economics","marketing","hr","supply chain","commerce"],
    "medical": ["mbbs","medicine","bds","dentistry","pharmacy","nursing","dpt","biotech","biochemistry"],
    "social_science": ["psychology","education","sociology","political","international relations","mass communication","journalism","media"],
}
def _canon_field(s: str) -> str:
    x = _norm(s)
    for k, vals in FIELD_ALIASES.items():
        if any(v in x for v in vals): return k
    return "computer_science" if "computer" in x or "software" in x else _norm(s)

def main():
    if not F_PROGS.exists():
        raise FileNotFoundError(f"Missing programs CSV: {F_PROGS}")
    dfp = pd.read_csv(F_PROGS).fillna("")
    dfp.columns = [c.strip().lower() for c in dfp.columns]

    # Ensure baseline columns
    for need in ["university_name","city","province","program_name","degree_level","field_category","apply_url","fee_per_year"]:
        if need not in dfp.columns: dfp[need] = ""

    dfp = dfp.rename(columns={
        "degree_level":"level",
        "field_category":"field",
        "university":"university_name",
        "fee":"fee_per_year",
    })

    dfp['semester_fee'] = dfp['semester_fee']  # Fetch semester_fee from the DB (no calculation needed)

    # Optional uni-level file (adds cleaner city/province if available)
    dfe = pd.read_csv(F_UNIS).fillna("").rename(columns={"university":"university_name"}) if F_UNIS.exists() else pd.DataFrame()

    # Wikipedia/HEC merge (adds website/programs_detected/offers_FEST/ranking if available)
    dfw = pd.read_csv(F_WIKI).fillna("") if F_WIKI.exists() else pd.DataFrame()

    # Build keys
    dfp["univ_key"] = dfp["university_name"].apply(_key)
    if not dfe.empty: dfe["univ_key"] = dfe["university_name"].apply(_key)
    if not dfw.empty: dfw["univ_key"] = dfw["university_name"].apply(_key)

    # Universities table
    # === Universities table (drive from wiki/HEC if present) ===
    if not dfw.empty:
    # Start from scraped list so we don’t limit to FEST-only sample
        cols_keep = [c for c in ["university_name","website_url","offers_FEST","wiki_url"] if c in dfw.columns]
        df_uni = dfw[cols_keep].drop_duplicates().copy()

    # Attach city / province from programs file when available
        if "university_name" in dfp.columns:
            city_map     = dfp.groupby("university_name")["city"].first()
            province_map = dfp.groupby("university_name")["province"].first()
            df_uni["city"]     = df_uni["university_name"].map(city_map)
            df_uni["province"] = df_uni["university_name"].map(province_map)
    else:
    # Fallback: build from programs if wiki/HEC is missing
        df_uni = dfp[["university_name","city","province"]].drop_duplicates().copy()

# Key + defaults
    df_uni["univ_key"] = df_uni["university_name"].apply(_key)
    for col, default in [("type",""),("ranking",""),("website_url",""),("offers_FEST",False)]:
        if col not in df_uni.columns:
            df_uni[col] = default

# Final tidy columns
    df_uni = df_uni.drop_duplicates(subset=["university_name"])[
        ["university_name","city","province","type","ranking","website_url","offers_FEST"]
    ]

    # add simple ranking tier if missing
    if "ranking" not in df_uni.columns: df_uni["ranking"] = ""
    if "website_url" not in df_uni.columns: df_uni["website_url"] = ""
    if "offers_FEST" not in df_uni.columns: df_uni["offers_FEST"] = False

    # Clean and write
    df_uni = df_uni.drop_duplicates(subset=["university_name"])[["university_name","city","province","type","ranking","website_url","offers_FEST"]]
    df_uni.to_csv(OUT_UNI, index=False)
    print(f"✅ universities_clean.csv → {len(df_uni)} rows")

    # Programs table
    dfp["level_norm"] = dfp.apply(lambda r: _canon_level(str(r.get("level","")), str(r.get("program_name",""))), axis=1)
    dfp["field_norm"] = dfp["field"].apply(_canon_field)

    # attach website_url to programs
    dfp = dfp.merge(df_uni.assign(univ_key=lambda d: d["university_name"].apply(_key))[["univ_key","website_url","offers_FEST"]],
                    on="univ_key", how="left")

    # tidy columns
    keep = ["university_name","city","province","program_name","level","field","level_norm","field_norm","fee_per_year", "semester_fee","apply_url","website_url","offers_FEST"]
    for k in keep:
        if k not in dfp.columns: dfp[k] = ""

    dfp = dfp[keep]
    dfp.to_csv(OUT_PRO, index=False)
    print(f"✅ programs_clean.csv → {len(dfp)} rows")

if __name__ == "__main__":
    main()
