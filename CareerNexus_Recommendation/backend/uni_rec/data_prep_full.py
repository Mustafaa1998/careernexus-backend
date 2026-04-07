from __future__ import annotations
import os, re
from pathlib import Path
import pandas as pd

DATA = Path("data")
F_WIKI = DATA / "hec_fest_universities.csv"        # from your wiki/HEC scraper (172+ rows)
F_UNI  = DATA / "universities_clean.csv"           # old clean unis (fallback)
F_PROG = DATA / "programs_clean.csv"               # current programs (600 rows)
F_FEST_UNIS = DATA / "fest_universities_master.csv"
F_FEST_PROG = DATA / "programs_fest_clean.csv"

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()

def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(name))

# Canonical program synonyms (used when generating synthetic program rows)
IT_SYNS = ["computer science","software engineering","data science","artificial intelligence","information technology"]
ENG_SYNS = ["electrical engineering","mechanical engineering","civil engineering","computer engineering","chemical engineering"]
SCI_SYNS = ["physics","chemistry","mathematics","statistics","biotechnology","biochemistry","environmental science"]

def _detect_fest_bucket(program_name: str, field: str) -> str:
    p = _norm(program_name)
    f = _norm(field)
    if "engineering" in p or f == "engineering":
        return "Engineering"
    if any(k in p for k in ["computer", "software", "data science", "artificial intelligence", "computing", "information technology"]) or f == "computer_science":
        return "IT/CS"
    if any(k in p for k in ["physics","chem","math","statistics","biotech","zoology","botany","environment","materials","geology","earth"]):
        return "Sciences"
    return ""

def _canon_field(program_name: str) -> str:
    p = _norm(program_name)
    if "engineering" in p:
        return "engineering"
    if any(k in p for k in ["computer","software","data science","artificial intelligence","computing","information technology"]):
        return "computer_science"
    if any(k in p for k in ["physics","chemistry","mathematics","statistics","biotech","biochemistry","environment"]):
        return "sciences"
    return ""

def build():
    # ---- Load sources ----
    dfw = pd.read_csv(F_WIKI).fillna("") if F_WIKI.exists() else pd.DataFrame()
    dfu = pd.read_csv(F_UNI).fillna("")  if F_UNI.exists()  else pd.DataFrame()
    dfp = pd.read_csv(F_PROG).fillna("") if F_PROG.exists() else pd.DataFrame()

    # Normalize columns
    for df in (dfw, dfu, dfp):
        if not df.empty:
            df.columns = [c.strip().lower() for c in df.columns]

    # ---- Universities master ----
    # Load university data (same as before)
    if not dfw.empty:
        cols = [c for c in ["university_name","city","province","website_url","offers_FEST","wiki_url","programs_detected"] if c in dfw.columns]
        df_uni = dfw[cols].drop_duplicates().copy()
    elif not dfu.empty:
        df_uni = dfu[["university_name","city","province","website_url"]].drop_duplicates().copy()
        df_uni["offers_FEST"] = ""
        df_uni["wiki_url"] = ""
        df_uni["programs_detected"] = ""
    else:
        print("⚠️ No university source found. Aborting.")
        return

    df_uni["univ_key"] = df_uni["university_name"].apply(_key)

    # ---- Programs base (existing program rows) ----
    if not dfp.empty:
        need = ["university_name","city","province","program_name","level","field","fee_per_year","apply_url","website_url"]
        for c in need:
            if c not in dfp.columns: dfp[c] = ""
        base_prog = dfp.copy()
    else:
        base_prog = pd.DataFrame(columns=["university_name","city","province","program_name","level","field","fee_per_year","apply_url","website_url"])

    # ---- Auto-generate missing program rows from scraped “programs_detected” ----
    synth_rows = []
    names_in_prog = set(_norm(x) for x in base_prog["university_name"]) if not base_prog.empty else set()
    for _, u in df_uni.iterrows():
        uname = u.get("university_name","")
        if _norm(uname) in names_in_prog:
            continue  # already has at least some programs

        detected = str(u.get("programs_detected","")).strip()
        if not detected:
            # be generous: seed a minimal FEST set so uni shows up in IT or ENG queries
            seed = IT_SYNS[:2] + ENG_SYNS[:2] + SCI_SYNS[:1]
        else:
            seed = [x.strip() for x in detected.split(",") if x.strip()]

        for prog in seed:
            synth_rows.append({
                "university_name": uname,
                "city": u.get("city",""),
                "province": u.get("province",""),
                "program_name": prog.title(),
                "level": "",  # unknown → let your API infer “BS” when user asks for BS
                "field": _canon_field(prog),
                "fee_per_year": "",
                "apply_url": "",
                "website_url": u.get("website_url",""),
            })

    df_synth = pd.DataFrame(synth_rows) if synth_rows else pd.DataFrame(columns=base_prog.columns)
    df_all_prog = pd.concat([base_prog, df_synth], ignore_index=True)

    # ---- FEST filter & bucket ----
    df_all_prog["fest_bucket"] = df_all_prog.apply(lambda r: _detect_fest_bucket(r.get("program_name",""), r.get("field","")), axis=1)
    df_all_prog = df_all_prog[df_all_prog["fest_bucket"] != ""].copy()

    # ---- Add semester_fee directly from the database ----
    # Fetch semester_fee directly from the database
    df_all_prog['semester_fee'] = df_all_prog['semester_fee']  # Use the semester_fee from DB, assuming it is fetched

    # ---- Build FEST universities master (with sample programs) ----
    cats = (df_all_prog.groupby("university_name")["fest_bucket"]
                  .apply(lambda s: ",".join(sorted(set(s)))).reset_index()
                  .rename(columns={"fest_bucket":"fest_categories"}))

    sample = (df_all_prog.groupby("university_name")["program_name"]
                     .apply(lambda s: ", ".join(list(dict.fromkeys([p.title() for p in s if p][:10]))))
                     .reset_index()
                     .rename(columns={"program_name":"sample_programs"}))

    fest_unis = (df_uni.merge(cats, on="university_name", how="inner")
                      .merge(sample, on="university_name", how="left"))

    # ---- Write outputs (safe overwrite) ----
    for p in (F_FEST_UNIS, F_FEST_PROG):
        try:
            if p.exists(): os.remove(p)
        except Exception:
            pass

    fest_unis[["university_name","city","province","website_url","fest_categories","sample_programs"]].drop_duplicates().to_csv(F_FEST_UNIS, index=False)

    keep = ["university_name","city","province","program_name","level","field","fee_per_year","semester_fee","apply_url","website_url","fest_bucket"]
    for c in keep:
        if c not in df_all_prog.columns:
            df_all_prog[c] = ""
    df_all_prog[keep].drop_duplicates().to_csv(F_FEST_PROG, index=False)

    print(f"✅ {F_FEST_UNIS.name} → {len(fest_unis)} rows")
    print(f"✅ {F_FEST_PROG.name} → {len(df_all_prog)} rows")

if __name__ == "__main__":
    build()
