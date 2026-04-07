"""
parse_any_resume_hybrid.py
--------------------------------
Reads any resume (PDF/DOCX), uses your fine-tuned spaCy model for NER,
then applies strict post-processing to output clean JSON.

Usage:
  python ner_training/parse_any_resume_hybrid.py "C:/Users/Hp/Desktop/HANIA ALI ALVI.pdf"
"""

import sys, os, json, re
from pathlib import Path
import spacy

# Ensure project root on path
sys.path.append(os.path.abspath("."))

from resume_parser.parser import read_pdf_text, read_docx_text
from resume_parser.utils import get_extension, clean_whitespace
from resume_parser.preprocessing import normalize_text, split_sections
from resume_parser.patterns import (
    EMAIL_RE, PHONE_RE, YEAR_RE, DATE_RANGE_RE,
    NAME_LINE_RE, ALLCAPS_NAME_RE
)
from resume_parser.extractors import extract_email, extract_phone, extract_languages, extract_summary

MODEL_PATH = Path("ner_training/models/resume_ner_300")

# -------- Helpers / filters --------
HEADING_WORDS = {
    "profile","summary","experience","education","projects","skills","technical skills",
    "soft skills","research","certifications","languages","achievements","references"
}

def is_heading(s: str) -> bool:
    t = re.sub(r"[^A-Za-z ]+", " ", s).strip().lower()
    return t in HEADING_WORDS or t.replace(" ","") in {"technicalskills","softskills"}

def dedupe_keep_order(items):
    seen = set(); out = []
    for x in items:
        k = x.strip().lower()
        if k and k not in seen:
            seen.add(k); out.append(x.strip())
    return out

def smart_name(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Prefer first ALL-CAPS title (<=3 words) near top
    for ln in lines[:8]:
        if ALLCAPS_NAME_RE.match(ln) and len(ln.split()) <= 3 and not is_heading(ln):
            return ln.title()
    # Try line above email
    email = extract_email(text)
    if email:
        for i, ln in enumerate(lines):
            if email in ln and i-1 >= 0:
                cand = lines[i-1]
                if (ALLCAPS_NAME_RE.match(cand) or NAME_LINE_RE.match(cand)) and not is_heading(cand):
                    return cand.title() if ALLCAPS_NAME_RE.match(cand) else cand
                break
    # Fallback: Title Case line near top
    for ln in lines[:8]:
        if NAME_LINE_RE.match(ln) and not is_heading(ln):
            return ln
    return None

def tidy_multi_line(val: str) -> str:
    # collapse newlines and bullet separators into single spaces
    v = val.replace("|"," ").replace("•"," ").replace("—","-").replace("–","-")
    v = re.sub(r"[\r\n]+", " ", v)
    v = re.sub(r"\s{2,}", " ", v).strip()
    return v

def separate_email_phone_if_glued(s: str) -> list[str]:
    # Split cases like "0312... email@x.com" into two items
    out = []
    # emails
    for m in EMAIL_RE.finditer(s):
        out.append(m.group(0))
    # phones (avoid catching page codes)
    for m in PHONE_RE.finditer(s):
        out.append(re.sub(r"[^\d+]", "", m.group(0)))
    # if neither matched, return original
    return out if out else [s]

# -------- Experience & Education parsing --------
def parse_experience_block(text: str) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out = []
    for i, ln in enumerate(lines):
        if DATE_RANGE_RE.search(ln) or re.search(r"(?i)\b(present|current)\b", ln):
            pre = ln
            m = YEAR_RE.search(ln)
            if m: pre = ln[:m.start()].strip()
            role, company = None, None
            if pre:
                if "," in pre:
                    parts = [p.strip() for p in pre.split(",", 1)]
                    role, company = parts[0] or None, parts[1] or None
                else:
                    role = pre
            if not role and i-1 >= 0:
                prv = lines[i-1]
                if "," in prv:
                    parts = [p.strip() for p in prv.split(",", 1)]
                    role, company = parts[0] or None, parts[1] or None
                else:
                    role = prv
            ys = YEAR_RE.findall(ln)
            start_year = int(ys[0]) if ys else None
            end_year = int(ys[-1]) if (ys and len(ys) > 1) else None
            if re.search(r"(?i)\b(present|current|now)\b", ln): end_year = None
            out.append({
                "title": role or None,
                "company": company or None,
                "date_range": tidy_multi_line(ln),
                "start_year": start_year,
                "end_year": end_year
            })
    return out

def parse_education_block(text: str) -> list[dict]:
    inst_hint = re.compile(r"(?i)\b(University|Institute|College|School|Academy)\b")
    degree_hint = re.compile(
        r"(?i)\b(Bachelor|Bachelors|Master|Masters|BSc|BS|MSc|MS|PhD|MBA|MPhil|BA|MA|BBA|BCom|MCom|Intermediate|Matriculation)\b"
    )
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    n = len(lines)
    rows = []
    for i, ln in enumerate(lines):
        if inst_hint.search(ln):
            year = None
            y0 = YEAR_RE.search(ln)
            if y0: year = int(y0.group(0))
            elif i+1 < n:
                y1 = YEAR_RE.search(lines[i+1])
                if y1: year = int(y1.group(0))
            degree = None
            for j in range(i-1, max(i-3,-1), -1):
                if degree_hint.search(lines[j]):
                    degree = re.sub(r"\s{2,}", " ", lines[j]); break
            if not degree and i+1 < n and degree_hint.search(lines[i+1]):
                degree = re.sub(r"\s{2,}", " ", lines[i+1])
            rows.append({
                "degree": degree,
                "institution": tidy_multi_line(ln),
                "year": year
            })
    uniq, seen = [], set()
    for r in rows:
        key = (r.get("degree") or "", r.get("institution") or "", r.get("year") or 0)
        if key not in seen:
            seen.add(key); uniq.append(r)
    return uniq

# -------- NER sanitization --------
def sanitize_ner_entities(doc_text: str, ents):
    buckets: dict[str, list[str]] = {}
    for e in ents:
        val = tidy_multi_line(e.text)
        lab = e.label_
        if not val: continue
        if is_heading(val):  # drop section headers
            continue
        if len(val) > 80:   # drop long chunks
            continue
        # Split any glued email/phone candidates observed as SKILL/ORG etc.
        if "@" in val or re.search(r"\d{4,}", val):
            parts = separate_email_phone_if_glued(val)
            for p in parts:
                buckets.setdefault(lab, []).append(p.strip())
        else:
            buckets.setdefault(lab, []).append(val)

    # Override EMAIL/PHONE from regex (ground truth)
    email = extract_email(doc_text)
    phone = extract_phone(doc_text)
    if email:
        buckets["EMAIL"] = [email]
    if phone:
        buckets["PHONE"] = [phone]

    # Clean SKILL noise: remove pure headings / multi-word phrases > 6 tokens
    skills = [s for s in buckets.get("SKILL", []) if not is_heading(s) and 1 <= len(s.split()) <= 6]
    skills = [s for s in skills if not re.fullmatch(r"[A-Z ]{3,}", s)]
    buckets["SKILL"] = dedupe_keep_order(skills)

    # Clean ORG
    orgs = [o for o in buckets.get("ORG", []) if not is_heading(o) and 1 <= len(o.split()) <= 6]
    buckets["ORG"] = dedupe_keep_order(orgs)

    # Clean DESIGNATION: short job titles (<= 6 tokens), drop obvious headings
    desigs = [d for d in buckets.get("DESIGNATION", []) if not is_heading(d) and 1 <= len(d.split()) <= 6]
    buckets["DESIGNATION"] = dedupe_keep_order(desigs)

    # EXPERIENCE: keep ranges or "N years"
    exps = []
    for x in buckets.get("EXPERIENCE", []):
        if DATE_RANGE_RE.search(x) or re.search(r"\b\d+\s+years?\b", x, re.I):
            exps.append(x)
    buckets["EXPERIENCE"] = dedupe_keep_order(exps)

    # NAME: prefer header heuristic
    nm = smart_name(doc_text)
    if nm:
        buckets["NAME"] = [nm]
    else:
        buckets["NAME"] = buckets.get("NAME", [])[:1]

    return buckets

# -------- Main parse --------
def parse_resume(path_str: str) -> dict:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(path)

    ext = get_extension(path)
    if ext == ".pdf":
        raw = read_pdf_text(path)
    elif ext == ".docx":
        raw = read_docx_text(path)
    else:
        raise ValueError("Only .pdf and .docx supported.")

    text = normalize_text(clean_whitespace(raw))
    if not text.strip():
        return {"error": "No text extracted (possibly scanned PDF)"}

    nlp = spacy.load(MODEL_PATH)
    doc = nlp(text)

    # Cleaned entity buckets
    buckets = sanitize_ner_entities(text, doc.ents)

    # Sections for rule-based parsing of education/experience
    sections = split_sections(text)
    edu_block = sections.get("education", text)
    exp_block = sections.get("experience", text)

    education = parse_education_block(edu_block)
    experience = parse_experience_block(exp_block)

    result = {
        "filename": path.name,
        "name": (buckets.get("NAME") or [None])[0],
        "email": (buckets.get("EMAIL") or [None])[0],
        "phone": (buckets.get("PHONE") or [None])[0],
        "location": None,
        "summary": extract_summary(text),
        "education": education,
        "experience": experience,
        "skills": buckets.get("SKILL", []),
        "certifications": [],
        "languages": extract_languages(text),
        "raw_text_preview": "\n".join(text.splitlines()[:120]),
    }
    return result

def main():
    if len(sys.argv) < 2:
        print("Usage: python ner_training/parse_any_resume_hybrid.py <path_to_resume>")
        sys.exit(1)
    file_path = sys.argv[1]
    # Silence pdfminer color warnings
    os.environ["PYTHONWARNINGS"] = "ignore"
    data = parse_resume(file_path)
    print(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
