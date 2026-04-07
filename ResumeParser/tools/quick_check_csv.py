# tools/quick_check_csv.py
import pandas as pd
from pathlib import Path

CSV = Path(r"D:\ResumeParser\data\raw\pakistani_resumes_23000.csv")
df = pd.read_csv(CSV, nrows=50000, encoding="utf-8", low_memory=False)

print("Columns:", list(df.columns))

# Try common text columns
candidates = [c for c in df.columns if c.lower() in {"resume","resume_text","text","content","body"}]
if not candidates:
    # Fallback: guess by longest average length
    candidates = sorted(df.columns, key=lambda c: df[c].astype(str).str.len().mean(), reverse=True)[:3]

print("Likely text columns:", candidates)
