# backend/uni_recommedationold/backfill_norms.py
from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select

from .database import engine
from .models import Program
from .loader import _canon_field, _canon_program

def _canon_level(x: str) -> str:
    x = (x or "").strip().lower()
    if x in {"bs", "be", "bsc", "bachelor", "bachelors"}:
        return "bs"
    if x in {"ms", "msc", "m.sc", "mphil", "master", "masters"}:
        return "ms"
    if x in {"phd", "doctoral", "doctorate"}:
        return "phd"
    # try to infer from free text
    if "phd" in x or "doctoral" in x: return "phd"
    if "ms" in x or "m.sc" in x or "master" in x or "mphil" in x: return "ms"
    if "bs" in x or "b.sc" in x or "be" in x or "bachelor" in x: return "bs"
    return ""

def main():
    with Session(bind=engine) as session:
        rows = session.execute(select(Program)).scalars().all()
        updated = 0
        for p in rows:
            # fill program_norm from program_name (fallback to itself)
            pn = (p.program_name or "").strip()
            if not p.program_norm:
                p.program_norm = _canon_program(pn)

            # fill level_norm from degree_level
            if not p.level_norm:
                p.level_norm = _canon_level(p.degree_level or "")

            # fill field_norm from field_category
            fc = (p.field_category or "").strip()
            if not p.field_norm and fc:
                p.field_norm = _canon_field(fc)

            updated += 1
            if updated % 500 == 0:
                session.commit()
        session.commit()
        print(f"✅ Backfilled norms for {updated} programs.")

if __name__ == "__main__":
    main()
