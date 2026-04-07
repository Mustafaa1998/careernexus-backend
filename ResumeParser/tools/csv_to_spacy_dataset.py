# tools/csv_to_spacy_dataset.py
# Convert structured resume CSV directly to a spaCy training dataset (no Doccano needed)

import pandas as pd, re, json, random
from pathlib import Path
import spacy
from spacy.tokens import DocBin

LABEL_MAP = {
    "Name": "NAME",
    "Email": "EMAIL",
    "Phone": "PHONE",
    "Location": "LOCATION",
    "Degree": "EDUCATION",
    "CollegeName": "ORG",
    "GraduationYear": "EDUCATION",
    "Designation": "DESIGNATION",
    "CompaniesWorkedAt": "ORG",
    "YearsOfExperience": "EXPERIENCE",
    "Skills": "SKILL",
}

def as_list(val):
    if not val or str(val).lower().strip() in {"nan", "none", "null"}:
        return []
    return re.split(r"[,;/\n|]+", str(val))

def find_spans(text, phrase):
    spans = []
    if not phrase:
        return spans
    phrase = str(phrase).strip()
    start = 0
    while True:
        i = text.lower().find(phrase.lower(), start)
        if i == -1:
            break
        spans.append((i, i + len(phrase)))
        start = i + len(phrase)
    return spans

def main():
    SRC = Path(r"D:\ResumeParser\data\raw\pakistani_resumes_23000.csv")
    OUT_DIR = Path(r"D:\ResumeParser\data\spacy_dataset")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(SRC, encoding="utf-8", low_memory=False)
    rows = df.to_dict(orient="records")
    random.shuffle(rows)

    nlp = spacy.blank("en")
    db_train, db_dev = DocBin(), DocBin()

    split = int(len(rows) * 0.9)

    for idx, r in enumerate(rows):
        text_parts = [
            str(r.get("Name") or ""),
            str(r.get("Designation") or ""),
            f"Email: {r.get('Email') or ''} | Phone: {r.get('Phone') or ''} | Location: {r.get('Location') or ''}",
            f"Education: {r.get('Degree') or ''} at {r.get('CollegeName') or ''} ({r.get('GraduationYear') or ''})",
            f"Experience: {r.get('Designation') or ''} at {r.get('CompaniesWorkedAt') or ''} ({r.get('YearsOfExperience') or ''} years)",
            f"Skills: {r.get('Skills') or ''}",
        ]
        text = "\n".join([t for t in text_parts if t.strip()])

        ents = []
        for col, label in LABEL_MAP.items():
            val = r.get(col)
            if not val or str(val).strip().lower() in {"nan","none","null"}:
                continue
            if col in {"Skills", "CompaniesWorkedAt"}:
                for token in as_list(val):
                    for (s, e) in find_spans(text, token):
                        ents.append((s, e, label))
            else:
                for (s, e) in find_spans(text, val):
                    ents.append((s, e, label))

        # Remove overlapping spans
        ents.sort(key=lambda x: x[0])
        clean = []
        last_end = -1
        for s, e, lab in ents:
            if s >= last_end:
                clean.append((s, e, lab))
                last_end = e

        doc = nlp.make_doc(text)
        ents_final = []
        for s, e, lab in clean:
            span = doc.char_span(s, e, label=lab)
            if span:
                ents_final.append(span)
        doc.ents = ents_final

        if idx < split:
            db_train.add(doc)
        else:
            db_dev.add(doc)

    db_train.to_disk(OUT_DIR / "train.spacy")
    db_dev.to_disk(OUT_DIR / "dev.spacy")

    print(f"✅ Saved training data to {OUT_DIR}")
    print(f"Train: {len(db_train)} examples | Dev: {len(db_dev)} examples")

if __name__ == "__main__":
    main()
