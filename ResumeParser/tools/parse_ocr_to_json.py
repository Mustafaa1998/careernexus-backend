# tools/parse_ocr_to_json.py
from __future__ import annotations
import sys, json, re, pathlib

# make project root importable
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# use your existing OCR util
from resume_parser.ocr import pdf_to_text_via_ocr

# ---------------------------
# Text cleanup & formatting
# ---------------------------

HEADING_VARIANTS = [
    # core
    r"PROFILE", r"SUMMARY",
    r"EXPERIENCE", r"WORK EXPERIENCE", r"PROFESSIONAL EXPERIENCE",
    r"EDUCATION", r"ACADEMICS",
    r"PROJECTS", r"PERSONAL PROJECTS",
    # skills families
    r"SKILLS", r"TECHNICAL SKILLS", r"SOFTWARE SKILLS", r"SOFT SKILLS",
    # credentials/trainings
    r"CERTIFICATIONS", r"CERTIFICATION", r"COURSES", r"TRAININGS",
    # extras seen in your data
    r"VOLUNTARY", r"VOLUNTARY & EXTRA-CURRICULAR ACTIVITIES",
    r"ADDITIONAL QUALIFICATION"
]

# Allow headings even with leading spaces and small trailing noise
HEADING_RE = re.compile(
    r"(?im)^\s*(?:\b)?(%s)\b[^\n]*$" % "|".join(HEADING_VARIANTS)
)

BULLET_RE = re.compile(r"(?m)^\s*([•\-–·]|\*|e\s)\s*")  # keeps 'e ' bullets too


def ensure_heading_lines(text: str) -> str:
    """
    1) Keep your original 'ee' tokens untouched (as requested).
    2) Force headings onto their own line, then add exactly one blank line after.
    3) Preserve line breaks for bullets and short lines, otherwise reflow paragraphs.
    """
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Put headings on their own line with a blank line after
    lines = text.split("\n")
    fixed_lines = []
    for line in lines:
        m = HEADING_RE.match(line.strip())
        if m:
            hd = m.group(1).upper()
            fixed_lines.append(hd)
            fixed_lines.append("")  # blank line after heading
        else:
            fixed_lines.append(line)
    text = "\n".join(fixed_lines)

    # Reflow long lines a little, but preserve bullets and short lines
    out = []
    for raw in text.split("\n"):
        if HEADING_RE.match(raw.strip()):
            out.append(raw.strip().upper())
            continue
        if BULLET_RE.match(raw) or len(raw.strip()) <= 60:
            out.append(raw.rstrip())
        else:
            if out and out[-1] and not HEADING_RE.match(out[-1]) and not BULLET_RE.match(out[-1]):
                out[-1] = (out[-1].rstrip() + " " + raw.strip())
            else:
                out.append(raw.strip())
    return "\n".join(out)


# ---------------------------
# Sectionizer
# ---------------------------

def split_sections(text: str) -> dict[str, str]:
    """
    Grab text under each known heading until the next heading.
    Returns raw section blocks (you can further parse skills/education if you want).
    """
    pat = re.compile(
        r"(?mis)^\s*(%s)\b[^\n]*\n+(.*?)(?=^\s*(?:%s)\b|\Z)"
        % ("|".join(HEADING_VARIANTS), "|".join(HEADING_VARIANTS))
    )
    sections = {}
    for m in pat.finditer(text):
        hd = m.group(1).upper()
        content = m.group(2).strip()
        sections[hd] = content
    return sections


# ---------------------------
# Field extractors (simple)
# ---------------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", re.I)
PHONE_RE = re.compile(
    r"(?:(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3,4}\)?)[-.\s]?\d{3}[-.\s]?\d{3,4})", re.I
)

def extract_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None

def extract_phone(text: str) -> str | None:
    top = "\n".join(text.split("\n")[:10])
    m = PHONE_RE.search(top) or PHONE_RE.search(text)
    if not m:
        return None
    num = re.sub(r"\s+", " ", m.group(0)).strip()
    num = re.sub(r"[–—]", "-", num)
    return num

def extract_name(text: str) -> str | None:
    # crude: look near the top; grab a likely ALL-CAPS 2–4 words string
    first = "\n".join(text.split("\n")[:5])
    cand = re.findall(r"(?m)^[A-Z][A-Z\s'.\-]{3,}$", first)
    if cand:
        return sorted(cand, key=len, reverse=True)[0].strip()
    return None


# ---------------------------
# Section post-processing
# ---------------------------

DEGREE_WORDS = r"(BACHELOR|BS|BSC|BE|MS|MSC|MASTERS|INTERMEDIATE|HSSC|FSC|FA|MATRIC|SSC|HIGH SCHOOL|BBA|BSCS|MCOM)"
YEAR_RE = re.compile(r"(19|20)\d{2}")

def parse_education_block(raw: str) -> list[str]:
    if not raw:
        return []
    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    keep = []
    for l in lines:
        if re.search(DEGREE_WORDS, l, re.I) or YEAR_RE.search(l):
            keep.append(l)
    return keep or lines

def parse_skills_block(raw: str) -> list[str]:
    if not raw:
        return []
    bits = []
    for line in raw.split("\n"):
        line = re.sub(BULLET_RE, "", line).strip()
        parts = [p.strip() for p in re.split(r"[,\u2022;|/]", line) if p.strip()]
        bits.extend(parts)
    seen, out = set(), []
    for b in bits:
        key = b.lower()
        if key not in seen and 1 < len(b) <= 60:
            seen.add(key)
            out.append(b)
    return out

def parse_projects_block(raw: str) -> list[str]:
    if not raw:
        return []
    lines = [re.sub(BULLET_RE, "", l).strip() for l in raw.split("\n")]
    items = []
    buf = []
    for l in lines:
        if not l:
            if buf:
                items.append(" ".join(buf).strip())
                buf = []
            continue
        if re.match(r"^[A-Z][A-Za-z0-9\s\-()&/]+$", l) and len(l) < 80 and buf:
            items.append(" ".join(buf).strip())
            buf = [l]
        else:
            buf.append(l)
    if buf:
        items.append(" ".join(buf).strip())
    return [i for i in items if len(i) > 5]

def parse_experience_block(raw: str) -> str:
    return raw.strip()

def parse_certifications_block(raw: str) -> list[str]:
    if not raw:
        return []
    lines = [re.sub(BULLET_RE, "", l).strip() for l in raw.split("\n") if l.strip()]
    return lines


# ---------------------------
# Main
# ---------------------------

def parse_pdf_to_json(pdf_path: str) -> dict:
    raw_text = pdf_to_text_via_ocr(pdf_path) or ""
    if not raw_text.strip():
        return {"error": "No text extracted from OCR."}

    # format headings & keep structure
    formatted = ensure_heading_lines(raw_text)

    # pull sections
    sec = split_sections(formatted)

    summary = (sec.get("SUMMARY") or sec.get("PROFILE") or "").strip()
    experience = parse_experience_block(sec.get("EXPERIENCE", "") or sec.get("WORK EXPERIENCE", ""))
    education = parse_education_block(sec.get("EDUCATION", "") or sec.get("ACADEMICS", ""))
    projects = parse_projects_block(sec.get("PROJECTS", "") or sec.get("PERSONAL PROJECTS", ""))
    # merge all skill-like blocks
    skills = parse_skills_block(
        (
            sec.get("TECHNICAL SKILLS", "")
            + "\n"
            + sec.get("SOFTWARE SKILLS", "")
            + "\n"
            + sec.get("SOFT SKILLS", "")
            + "\n"
            + sec.get("SKILLS", "")
        ).strip()
    )
    certs = parse_certifications_block(
        (sec.get("CERTIFICATIONS", "") or sec.get("COURSES", "") or sec.get("TRAININGS", "")).strip()
    )

    # top-level fields
    name = extract_name(formatted)
    email = extract_email(formatted)
    phone = extract_phone(formatted)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "summary": summary,
        "experience": experience,
        "education": education,          # list[str]
        "projects": projects,            # list[str]
        "skills": skills,                # list[str]
        "certifications": certs,         # list[str]
        "raw_preview": "\n".join(formatted.split("\n")[:40])  # first ~40 lines for quick debug
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools\\parse_ocr_to_json.py <path_to_pdf> [out.json]")
        sys.exit(1)
    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) >= 3 else None
    data = parse_pdf_to_json(pdf)
    js = json.dumps(data, ensure_ascii=False, indent=2)
    if out:
        pathlib.Path(out).write_text(js, encoding="utf-8")
        print(f"✅ Wrote {out}")
    else:
        print(js)
