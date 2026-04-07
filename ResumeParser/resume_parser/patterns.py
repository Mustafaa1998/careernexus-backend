# resume_parser/patterns.py
import re

# -------- Contacts --------
EMAIL_RE = re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(
    r"""(?x)
    (?:
        (\+?\d{1,3}[\s-]?)?            # country code
        (?:\(?\d{2,4}\)?[\s-]?)        # area code
        \d{3,4}[\s-]?\d{3,4}           # local
    )
    """
)

# -------- Years / Ranges --------
YEAR_RE = re.compile(r"\b(19[7-9]\d|20\d{2}|2100)\b")

# Robust ranges: "2019 – 2022", "2022 - Present", etc.
DATE_RANGE_RE = re.compile(
    r"""(?ix)
    \b(19\d{2}|20\d{2})\b
    \s*[–—-]\s*
    \b(?:Present|Now|Current|19\d{2}|20\d{2})\b
    """
)

# -------- Names --------
# Title Case name lines
NAME_LINE_RE = re.compile(r"(?m)^\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s*$")
# ALL-CAPS name lines (e.g., "HAMNA FAROOQ")
ALLCAPS_NAME_RE = re.compile(r"(?m)^\s*([A-Z][A-Z\-]+(?:\s+[A-Z][A-Z\-]+){0,3})\s*$")

# -------- Locations (optional generic hint) --------
LOCATION_HINT_RE = re.compile(r"\b([A-Z][a-z]+(?:[ ,]+[A-Z][a-z]+)*)\b(?:,\s*[A-Z][a-z]+)?")

# -------- Education helpers --------
# Lines likely to be institutions
INSTITUTION_HINT_RE = re.compile(r"(?i)\b(University|Institute|College|School|Academy)\b")

# Lines likely to be degrees (handles natural phrases too)
DEGREE_HINT_RE = re.compile(
    r"(?i)\b("
    r"Bachelor|Bachelors|Master|Masters|PhD|MPhil|MBA|"
    r"BSc|BS|MSc|MS|BA|MA|BBA|B\.?Com|M\.?Com|"
    r"B\.?Eng|M\.?Eng|B\.?Pharm|M\.?Pharm|B\.?CS|M\.?CS|"
    r"Intermediate|Matriculation"
    r")\b"
)
