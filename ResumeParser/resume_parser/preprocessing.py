# resume_parser/preprocessing.py
from __future__ import annotations
import re

def normalize_text(text: str) -> str:
    """
    Light normalization: de-hyphenate line-break hyphens, unify bullets, trim.
    """
    t = text.replace("\r", "\n")
    # de-hyphenate word-breaks like "experi-\nence"
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    # unify bullets to a simple dash
    t = re.sub(r"[•·●♦▪■▶»-]", "-", t)
    return t.strip()

def split_sections(text: str) -> dict[str, str]:
    """
    Very light section splitter based on headings.
    """
    headings = [
        "summary", "objective", "education", "experience", "work experience",
        "skills", "projects", "certifications", "languages", "awards",
        "publications", "interests"
    ]
    # Build regex for headings (start of line)
    pattern = r"(?im)^(%s)\b[:\s]*$" % "|".join([re.escape(h) for h in headings])
    parts = re.split(pattern, text)
    # re.split yields [pre, H1, post1, H2, post2, ...]
    out: dict[str, str] = {}
    preface = parts[0].strip() if parts else ""
    if preface:
        out["preface"] = preface

    for i in range(1, len(parts), 2):
        h = parts[i].lower().strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        out[h] = content
    return out
