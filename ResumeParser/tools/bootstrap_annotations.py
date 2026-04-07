# tools/bootstrap_annotations.py
import pandas as pd, json, re
from pathlib import Path

from resume_parser.patterns import EMAIL_RE, PHONE_RE, DATE_RANGE_RE
from resume_parser.preprocessing import normalize_text
from resume_parser.utils import clean_whitespace
from resume_parser.extractors import load_skills_dictionary

CLEAN_CSV = Path(r"D:\ResumeParser\data\clean\resumes_clean.csv")
SKILLS    = load_skills_dictionary(r"D:\ResumeParser\resume_parser\resources\skills.json") or []

OUT = Path(r"D:\ResumeParser\data\boot\doccano_bootstrap.jsonl")
OUT.parent.mkdir(parents=True, exist_ok=True)

def spans(pattern, text, label):
    return [[m.start(), m.end(), label] for m in pattern.finditer(text)]

def skill_spans(text):
    labs = []
    for sk in SKILLS:
        for m in re.finditer(rf"(?i)\b{re.escape(sk)}\b", text):
            labs.append([m.start(), m.end(), "SKILL"])
    return labs

df = pd.read_csv(CLEAN_CSV)
with OUT.open("w", encoding="utf-8") as f:
    for t in df["text"].astype(str):
        txt = normalize_text(clean_whitespace(t))
        labels = []
        labels += spans(EMAIL_RE, txt, "EMAIL")
        labels += spans(PHONE_RE, txt, "PHONE")
        labels += spans(DATE_RANGE_RE, txt, "EXPERIENCE")
        labels += skill_spans(txt)
        f.write(json.dumps({"text": txt, "labels": labels}, ensure_ascii=False) + "\n")

print("Wrote:", OUT)
