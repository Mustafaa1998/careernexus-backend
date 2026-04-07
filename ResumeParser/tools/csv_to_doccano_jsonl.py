# tools/csv_to_doccano_jsonl.py
# Convert a *structured* resume CSV into a synthetic resume text with auto labels (Doccano JSONL).
# Works with columns: Name, Email, Phone, Location, Degree, CollegeName, GraduationYear,
#   Designation, CompaniesWorkedAt, YearsOfExperience, Skills, Certifications, Projects, Awards, Publications
#
# Usage (from project root):
#   python tools\csv_to_doccano_jsonl.py --src data\raw\pakistani_resumes_23000.csv --out data\boot\doccano_bootstrap_from_csv.jsonl --limit 5000
#
# After this, upload the JSONL to Doccano and correct/complete the labels.

import argparse
from pathlib import Path
import pandas as pd
import re
import json
import math

# Map CSV columns to label names we want in Doccano
LABEL_MAP = {
    "Name": "NAME",
    "Email": "EMAIL",
    "Phone": "PHONE",
    "Location": "LOCATION",
    "Degree": "EDUCATION",
    "CollegeName": "ORG",            # treated as institution/org
    "GraduationYear": "EDUCATION",   # we label the year span as EDUCATION context
    "Designation": "DESIGNATION",
    "CompaniesWorkedAt": "ORG",
    "YearsOfExperience": "EXPERIENCE",
    "Skills": "SKILL",
    "Certifications": None,  # optional: you can add a CERTIFICATION label later if you wish
    "Projects": None,
    "Awards": None,
    "Publications": None,
}

SECTION_TPL = """
{NAME}
{DESIGNATION_LINE}
Email: {EMAIL} | Phone: {PHONE} | Location: {LOCATION}

EDUCATION
{DEGREE_LINE}
{ORG_LINE}
Graduation Year: {GRAD_YEAR_LINE}

EXPERIENCE
{EXP_LINE}

SKILLS
{SKILLS_LINE}

CERTIFICATIONS
{CERTS_LINE}

PROJECTS
{PROJ_LINE}

AWARDS
{AWARDS_LINE}

PUBLICATIONS
{PUBS_LINE}
""".strip("\n")

def coalesce(*vals, default=""):
    for v in vals:
        if v and str(v).strip() and str(v).strip().lower() not in {"nan", "none", "null"}:
            return str(v).strip()
    return default

def as_list(val):
    if not val or str(val).strip().lower() in {"nan","none","null"}:
        return []
    txt = str(val).replace("\r", "\n")
    # Split on commas/semicolons/newlines/pipes
    parts = re.split(r"[,\n;|]+", txt)
    return [p.strip() for p in parts if p and p.strip()]

def find_spans(text: str, needle: str):
    """Return all (start, end) for exact needle in text, case-sensitive fallback to case-insensitive if exact fails."""
    spans = []
    if not needle:
        return spans
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            break
        spans.append((idx, idx + len(needle)))
        start = idx + len(needle)
    if spans:
        return spans
    # fallback: case-insensitive match
    lower_text = text.lower()
    lower_needle = needle.lower()
    start = 0
    while True:
        idx = lower_text.find(lower_needle, start)
        if idx == -1:
            break
        spans.append((idx, idx + len(needle)))
        start = idx + len(needle)
    return spans

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="CSV path, e.g. data\\raw\\pakistani_resumes_23000.csv")
    ap.add_argument("--out", required=True, help="Output JSONL for Doccano")
    ap.add_argument("--limit", type=int, default=0, help="Optional: limit number of rows")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(src, encoding="utf-8", low_memory=False)
    # standardize column names to exactly those in LABEL_MAP keys if possible
    # if your CSV uses different names, rename here:
    # df = df.rename(columns={"college_name":"CollegeName", ...})

    needed = list(LABEL_MAP.keys())
    missing = [c for c in needed if c not in df.columns]
    if missing:
        print("WARNING: Missing expected columns:", missing)

    rows = df.to_dict(orient="records")
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    n_written = 0
    with out.open("w", encoding="utf-8") as fout:
        for r in rows:
            name = coalesce(r.get("Name"))
            email = coalesce(r.get("Email"))
            phone = coalesce(r.get("Phone"))
            loc = coalesce(r.get("Location"))

            degree = coalesce(r.get("Degree"))
            college = coalesce(r.get("CollegeName"))
            grad_year = coalesce(r.get("GraduationYear"))

            desg = coalesce(r.get("Designation"))
            company = coalesce(r.get("CompaniesWorkedAt"))
            yoe = coalesce(r.get("YearsOfExperience"))

            skills = as_list(r.get("Skills"))
            certs = as_list(r.get("Certifications"))
            projs = as_list(r.get("Projects"))
            awards = as_list(r.get("Awards"))
            pubs = as_list(r.get("Publications"))

            # Build each section line
            designation_line = desg if desg else ""
            degree_line = degree if degree else ""
            org_line = college if college else ""
            grad_line = str(grad_year) if grad_year else ""
            exp_line = ""
            if desg or company or yoe:
                # Example: "Senior Analyst at ABC Ltd (3 years)"
                parts = []
                if desg:
                    parts.append(desg)
                if company:
                    parts.append(f"at {company}")
                if yoe:
                    parts.append(f"({yoe} years)")
                exp_line = " ".join(parts)

            skills_line = ", ".join(skills) if skills else ""
            certs_line = "; ".join(certs) if certs else ""
            proj_line = "; ".join(projs) if projs else ""
            awards_line = "; ".join(awards) if awards else ""
            pubs_line = "; ".join(pubs) if pubs else ""

            text = SECTION_TPL.format(
                NAME=name or "",
                DESIGNATION_LINE=designation_line,
                EMAIL=email or "",
                PHONE=phone or "",
                LOCATION=loc or "",
                DEGREE_LINE=degree_line,
                ORG_LINE=org_line,
                GRAD_YEAR_LINE=grad_line,
                EXP_LINE=exp_line,
                SKILLS_LINE=skills_line,
                CERTS_LINE=certs_line,
                PROJ_LINE=proj_line,
                AWARDS_LINE=awards_line,
                PUBS_LINE=pubs_line,
            ).strip()

            labels = []

            # Single-value fields
            for col, label in LABEL_MAP.items():
                if label is None:
                    continue
                val = r.get(col)
                if not val or str(val).strip().lower() in {"nan","none","null"}:
                    continue

                if col in {"Skills"}:
                    # Each skill is labeled individually
                    for sk in as_list(val):
                        for (s, e) in find_spans(text, sk):
                            labels.append([s, e, "SKILL"])
                elif col in {"CompaniesWorkedAt"}:
                    # Split companies by comma/semicolon/pipe/newline
                    for comp in as_list(val):
                        for (s, e) in find_spans(text, comp):
                            labels.append([s, e, "ORG"])
                elif col in {"Certifications"}:
                    # (Optional) If you want a CERTIFICATION label, rename LABEL_MAP key to "CERTIFICATION"
                    pass
                else:
                    sval = str(val).strip()
                    if sval:
                        for (s, e) in find_spans(text, sval):
                            labels.append([s, e, label])

            # Basic quality: ensure non-overlapping & inside text
            filtered = []
            for s, e, lab in labels:
                if 0 <= s < e <= len(text):
                    filtered.append([s, e, lab])

            # De-duplicate labels
            uniq = []
            seen = set()
            for le in filtered:
                t = tuple(le)
                if t not in seen:
                    seen.add(t)
                    uniq.append(le)

            rec = {"text": text, "labels": uniq}
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_written += 1

    print(f"Wrote {n_written} records to {out}")
    print("Upload this JSONL to Doccano → Sequence Labeling project → JSONL importer.")
    print("Then correct/complete labels (esp. NAME/EDUCATION/DESIGNATION), export spaCy JSON, and train.")
    
if __name__ == "__main__":
    main()
