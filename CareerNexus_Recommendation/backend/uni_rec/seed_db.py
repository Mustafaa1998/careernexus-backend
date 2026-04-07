# backend/uni_recommedationold/seed_db.py
from __future__ import annotations
import os, sys
from pathlib import Path
from typing import Dict

import pandas as pd
from sqlalchemy.orm import Session

# ------- robust imports (works for both direct and -m) -------
if __package__ is None or __package__ == "":
    # Direct: python seed_db.py (cwd = uni_recommedationold)
    sys.path.append(os.path.dirname(__file__))
    from database import engine, Base, DATABASE_URL, ensure_database_exists  # type: ignore
    from models import University, Program  # type: ignore
else:
    # Package: python -m uni_recommedationold.seed_db (cwd = backend)
    from .database import engine, Base, DATABASE_URL, ensure_database_exists
    from .models import University, Program

# --------------------------- helpers ---------------------------
DATA_DIR = Path(__file__).parent / "data"
CSV_UNIS  = DATA_DIR / "pakistan_fest_universities.csv"
CSV_PROGS = DATA_DIR / "pakistan_fest_programs.csv"

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"⚠️  Missing file: {path}")
        return pd.DataFrame()
    # robust read + trim
    df = pd.read_csv(path, encoding="utf-8", dtype=str).fillna("")
    for c in df.select_dtypes(include=["object"]).columns:
        df[c] = df[c].astype(str).str.strip()
    return df

def _norm_level(x: str) -> str:
    x = (x or "").lower()
    if "phd" in x or "doctor" in x: return "PhD"
    if "ms" in x or "m.s" in x or "m.sc" in x or "master" in x: return "MS"
    if "be" in x or "bs" in x or "b.e" in x or "b.sc" in x or "bachelor" in x: return "BS"
    return (x.upper() if x else "")

def _to_int_or_none(x: str):
    x = (x or "").replace(",", "").strip()
    return int(x) if x.isdigit() else None

# --------------------------- seeding ---------------------------
def seed_universities(session: Session) -> Dict[str, int]:
    dfu = _read_csv(CSV_UNIS)
    if dfu.empty:
        print("⚠️  No universities to import.")
        return {}

    dfu["univ_key"] = (
        dfu["university_name"].astype(str)
        .str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    )

    for need in ["province","city","type","website","apply_url","ranking_tier"]:
        if need not in dfu.columns: dfu[need] = ""

    # existing -> avoid duplicates
    existing = {u.univ_key: u.id for u in session.query(University.univ_key, University.id).all()}
    created_map: Dict[str,int] = {}
    added = 0

    for _, r in dfu.iterrows():
        key = r["univ_key"]
        if key in existing:
            created_map[key] = existing[key]
            continue
        u = University(
            university_name=r["university_name"],
            province=r["province"],
            city=r["city"],
            type=r["type"],
            website=r.get("website",""),
            apply_url=r.get("apply_url",""),
            ranking_tier=r.get("ranking_tier",""),
            univ_key=key,
        )
        session.add(u)
        session.flush()
        created_map[key] = u.id
        added += 1

    session.commit()
    print(f"✅ Universities: inserted {added}, total now {session.query(University).count()}")
    return created_map

def seed_programs(session: Session, key_to_id: Dict[str,int]):
    dfp = _read_csv(CSV_PROGS)
    if dfp.empty:
        print("⚠️  No programs to import.")
        return

    for need in ["university_name","program_name","degree_level","field_category",
                 "city","province","apply_url","fee_per_year","semester_fee","duration_years",
                 "eligibility","required_traits"]:
        if need not in dfp.columns: dfp[need] = ""

    dfp["univ_key"] = (
        dfp["university_name"].astype(str)
        .str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    )

    existing_prog = {
    (p.university_fk, p.program_name.lower(), (p.degree_level or "").lower())
    for p in session.query(Program.university_fk, Program.program_name, Program.degree_level).all()
    }

    # map: university_id (PK) -> (name, province, city)
    univ_meta = {
        uid: (uname, uprov, ucity)
        for uid, uname, uprov, ucity in session.query(
            University.id, University.university_name, University.province, University.city
        ).all()
        }



    inserted, skipped = 0, 0

    for _, r in dfp.iterrows():
        key = r["univ_key"]
        univ_id = key_to_id.get(key)
        if not univ_id:
            skipped += 1
            continue

        name = r["program_name"].strip()
        level = _norm_level(r["degree_level"])
        sig = (univ_id, name.lower(), level.lower())
        if sig in existing_prog:
            continue

        # Fill required NOT NULL columns from parent university if CSV cells are empty
        u_name, u_prov, u_city = univ_meta.get(univ_id, ("", "", ""))

        p = Program(
    # FK to University.id (your model field is university_fk, not university_id)
            university_fk=univ_id,

    # optional CSV id if you keep it
            university_id_csv=r.get("university_id", "") or None,

    # required NOT NULL columns — backfilled safely
            university_name=(r.get("university_name", "") or u_name).strip(),
            province=(r.get("province", "") or u_prov).strip(),
            city=(r.get("city", "") or u_city).strip(),

    # program fields
            program_name=name,
            degree_level=level,
            field_category=r["field_category"],
            duration_years=(int(r["duration_years"]) if str(r["duration_years"]).isdigit() else None),
            eligibility=r.get("eligibility",""),
            fee_per_year=_to_int_or_none(r.get("fee_per_year","")),
            semester_fee=_to_int_or_none(r.get("semester_fee", "")), 
            required_traits=r.get("required_traits",""),
            apply_url=r.get("apply_url",""),

    # safe to keep None if your model allows it
            program_norm=None,
            field_norm=None,
            level_norm=None,
        )

# optional: quick norms if you want them filled
# p.program_norm = name.lower()
# p.field_norm   = (r["field_category"] or "").lower()
# p.level_norm   = level.lower()

        session.add(p)

        inserted += 1
        if inserted % 200 == 0:
            session.commit()

    session.commit()
    print(f"✅ Programs: inserted {inserted} (skipped {skipped} unknown-university rows).")

def main():
    print("🔧 Creating tables if not exist...")
    ensure_database_exists(DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    print("✅ Tables ready.")

    with Session(bind=engine) as session:
        key_to_id = seed_universities(session)
        seed_programs(session, key_to_id)

if __name__ == "__main__":
    main()
