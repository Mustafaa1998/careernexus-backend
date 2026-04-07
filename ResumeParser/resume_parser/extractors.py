# resume_parser/extractors.py
from __future__ import annotations
from typing import List, Optional
import re
import json
import os
from rapidfuzz import fuzz, process

from .patterns import (
    EMAIL_RE, PHONE_RE, YEAR_RE, DATE_RANGE_RE,
    NAME_LINE_RE, ALLCAPS_NAME_RE, INSTITUTION_HINT_RE, DEGREE_HINT_RE
)
from .nlp import get_nlp
from .config import MIN_YEAR, MAX_YEAR, MIN_SKILL_SIMILARITY
from .preprocessing import split_sections

# ---------- helpers ----------
def first_match(regex: re.Pattern, text: str) -> Optional[str]:
    m = regex.search(text)
    return m.group(0) if m else None

def _dedupe(seq: list[str]) -> list[str]:
    seen = set()
    out = []
    for s in seq:
        k = s.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(s.strip())
    return out

# ---------- single-field extractors ----------
def extract_email(text: str) -> Optional[str]:
    return first_match(EMAIL_RE, text)

def extract_phone(text: str) -> Optional[str]:
    raw = first_match(PHONE_RE, text)
    if not raw:
        return None
    digits = re.sub(r"[^\d+]", "", raw)
    return digits if len(digits) >= 7 else raw

def extract_name(text: str) -> Optional[str]:
    """
    Prefer the first ALL-CAPS line near the top (<= 3 words) as the name.
    If the line above email/phone looks like a role ('Undergraduate' etc.), skip it.
    Fallback to Title Case or spaCy PERSON.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Prefer first ALL-CAPS line in first 6 lines
    for ln in lines[:6]:
        if ALLCAPS_NAME_RE.match(ln) and len(ln.split()) <= 3:
            return ln.title()

    # Try the line(s) above the first email/phone
    email = extract_email(text)
    if email:
        for i, ln in enumerate(lines):
            if email in ln:
                idx = i - 1
                if idx >= 0:
                    cand = lines[idx]
                    # If this looks like a role, step one more up
                    if re.search(r"(?i)\b(undergrad|undergraduate|student|engineer|developer|designer|scientist)\b", cand):
                        if idx - 1 >= 0:
                            cand2 = lines[idx - 1]
                            if ALLCAPS_NAME_RE.match(cand2) or NAME_LINE_RE.match(cand2):
                                return cand2.title() if ALLCAPS_NAME_RE.match(cand2) else cand2
                    if NAME_LINE_RE.match(cand) or ALLCAPS_NAME_RE.match(cand):
                        return cand.title() if ALLCAPS_NAME_RE.match(cand) else cand
                break

    # Scan first 8 lines for a Title Case name
    for ln in lines[:8]:
        if EMAIL_RE.search(ln) or PHONE_RE.search(ln):
            continue
        if NAME_LINE_RE.match(ln):
            return ln

    # Fallback: spaCy PERSON on header region
    nlp = get_nlp()
    doc = nlp(" ".join(lines[:50]))
    persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    if persons:
        return sorted(persons, key=lambda s: -len(s))[0].strip()
    return None

def extract_years(text: str) -> List[int]:
    years = [int(y) for y in YEAR_RE.findall(text)]
    return sorted({y for y in years if MIN_YEAR <= y <= MAX_YEAR})

# ---------- education ----------
def _is_degree_line(s: str) -> bool:
    return bool(DEGREE_HINT_RE.search(s))

def _is_institution_line(s: str) -> bool:
    return bool(INSTITUTION_HINT_RE.search(s))

def parse_education(section_text: str) -> List[dict]:
    """
    Pair Degree → Institution → Year using a short window.
    - Accept institution+year on the same line (e.g., 'Iqra University 2022 – Present').
    - Do NOT treat the next degree line as an institution.
    - If a line has a year and looks institutional (has 'University/College/School/Institute/Academy'),
      treat it as institution when the degree line lacked one.
    """
    lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]
    out: List[dict] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if _is_degree_line(ln):
            degree = re.sub(r"\s{2,}", " ", ln)
            institution = None
            year = None

            # same line institution/year
            if _is_institution_line(ln):
                institution = ln
            y_in_line = first_match(YEAR_RE, ln)
            if y_in_line:
                year = int(y_in_line)

            # lookahead 1–2 lines, but stop if next degree starts
            for la in lines[i + 1:i + 3]:
                if _is_degree_line(la):
                    break
                if _is_institution_line(la) and not institution:
                    institution = la
                if not year:
                    y_la = first_match(YEAR_RE, la)
                    if y_la:
                        year = int(y_la)
                # fallback: a line with a year and institution hint but not a degree
                if not institution and _is_institution_line(la) and not _is_degree_line(la):
                    institution = la

            out.append({"degree": degree, "institution": institution, "year": year})
        i += 1
    return out

# ---------- experience ----------
def parse_experience(section_text: str) -> List[dict]:
    """
    Handle single-line 'Role, Company 2021 – 2022' and two-line variants
    (title/company on previous line, date range on current line).
    """
    lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]
    out: List[dict] = []
    for i, ln in enumerate(lines):
        if DATE_RANGE_RE.search(ln):
            # Prefer parsing role/company from same line before first year
            pre = ln
            m = YEAR_RE.search(ln)
            if m:
                pre = ln[:m.start()].strip()

            role, company = None, None
            if pre:
                if "," in pre:
                    parts = [p.strip() for p in pre.split(",", 1)]
                    role = parts[0] or None
                    company = parts[1] or None
                else:
                    role = pre

            # If no role parsed from same line, look one line up
            if not role and i - 1 >= 0:
                prev = lines[i - 1]
                if "," in prev:
                    parts = [p.strip() for p in prev.split(",", 1)]
                    role = parts[0] or None
                    company = parts[1] or None
                else:
                    role = prev

            ys = YEAR_RE.findall(ln)
            start_year = int(ys[0]) if ys else None
            end_year = int(ys[-1]) if (ys and len(ys) > 1) else None
            if re.search(r"(?i)present|current|now", ln):
                end_year = None

            out.append({
                "title": role or None,
                "company": company or None,
                "date_range": ln,
                "start_year": start_year,
                "end_year": end_year
            })
    return out

# ---------- languages / summary / certs ----------
def extract_languages(text: str) -> List[str]:
    sections = split_sections(text)
    lang_txt = sections.get("languages", "")
    if not lang_txt:
        m = re.search(r"(?im)^languages?\s*:\s*(.+)$", text)
        if m:
            lang_txt = m.group(1)
    langs = [w.strip(" .;,-") for w in re.split(r"[,\n/;]", lang_txt) if 1 < len(w.strip()) < 40]
    return _dedupe(langs)

def extract_summary(text: str) -> Optional[str]:
    sections = split_sections(text)
    for key in ("summary", "objective", "preface"):
        if key in sections and sections[key]:
            lines = sections[key].splitlines()
            return " ".join(lines[:4]).strip()
    return None

def extract_certifications(text: str) -> List[str]:
    sections = split_sections(text)
    cert_txt = sections.get("certifications", "")
    if not cert_txt:
        cert_lines = [ln.strip() for ln in text.splitlines() if re.search(r"(?i)certificat|certified", ln)]
        cert_txt = "\n".join(cert_lines)
    certs = [ln.strip(" -•·") for ln in cert_txt.splitlines() if len(ln.strip()) > 3]
    return _dedupe(certs)

# ---------- skills ----------
def load_skills_dictionary(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "skills" in data:
        return [s.strip() for s in data["skills"] if s.strip()]
    if isinstance(data, list):
        return [s.strip() for s in data if isinstance(s, str) and s.strip()]
    return []

def extract_skills(text: str, skills_dict: list[str]) -> list[str]:
    if not skills_dict:
        return []
    words = set(re.findall(r"[A-Za-z][A-Za-z0-9.+#\-]{1,29}", text))
    found: set[str] = set()

    # exact case-insensitive first
    dict_lc = {s.lower(): s for s in skills_dict}
    for w in words:
        if w.lower() in dict_lc:
            found.add(dict_lc[w.lower()])

    # fuzzy for multi-word entries (lightweight)
    remaining = [s for s in skills_dict if " " in s and s not in found]
    if remaining:
        choices = list(words)
        for target in remaining:
            res = process.extractOne(target, choices, scorer=fuzz.token_set_ratio)
            if res:
                _best, score, _idx = res
                if score >= MIN_SKILL_SIMILARITY:
                    found.add(target)

    return sorted(found, key=lambda s: s.lower())

# ---------- location ----------
def load_gazetteer(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]

def extract_location(text: str, gazetteer: list[str]) -> Optional[str]:
    """
    Very light location inference: look for any gazetteer city in the top ~60 lines.
    """
    if not gazetteer:
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    head = " ".join(lines[:60])  # focus near header/contact
    for city in gazetteer:
        if re.search(rf"(?i)\b{re.escape(city)}\b", head):
            return city
    return None
