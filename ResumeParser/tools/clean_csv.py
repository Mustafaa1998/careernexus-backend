# tools/clean_csv.py
import pandas as pd
import re, hashlib
from pathlib import Path

SRC = Path(r"D:\ResumeParser\data\raw\pakistani_resumes_23000.csv")
OUT = Path(r"D:\ResumeParser\data\clean\resumes_clean.csv")
TEXT_COL = None  # ← fill this with your column name after running quick_check_csv

df = pd.read_csv(SRC, encoding="utf-8", low_memory=False)

if TEXT_COL is None:
    # Auto-pick if you forgot to set TEXT_COL
    cands = [c for c in df.columns if c.lower() in {"resume","resume_text","text","content","body"}]
    if not cands:
        cands = sorted(df.columns, key=lambda c: df[c].astype(str).str.len().mean(), reverse=True)
    TEXT_COL = cands[0]

s = df[TEXT_COL].astype(str)

def normalize(t: str) -> str:
    t = t.replace("\r", "\n")
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()

s = s.apply(normalize)

# keep only reasonably long resumes
s = s[s.str.len() >= 300]

# dedupe (case-insensitive)
finger = s.str.lower().apply(lambda x: hashlib.md5(x.encode("utf-8")).hexdigest())
s = s[~finger.duplicated()]

OUT.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame({"text": s}).to_csv(OUT, index=False, encoding="utf-8")
print("Saved:", OUT, "| rows:", len(s))
