"""
Resume Parsing Utilities
This module defines functions to extract key information from a resume text.
It uses spaCy's named entity recognition to identify names, organizations and
other entities, and simple keyword matching for skills. This implementation
is intentionally lightweight; real applications should train custom NER models
and expand the skills dictionary.
"""

import re
from typing import Dict, List

import spacy

# Define a simple list of skills to search for. Extend this list as needed.
SKILL_KEYWORDS = [
    "python", "java", "javascript", "c++", "c#", "sql", "html", "css",
    "react", "node", "django", "flask", "machine learning", "data analysis",
    "project management", "communication", "leadership"
]


def parse_resume(text: str, nlp) -> Dict[str, List[str]]:
    """Extract name, contact info, education, experience and skills from resume text.

    Args:
        text: Raw text extracted from the resume.
        nlp: A loaded spaCy language model.

    Returns:
        A dictionary with extracted fields.
    """
    doc = nlp(text)
    name = None
    email = None
    phone = None
    education = []
    experience = []
    skills = []

    # Extract email and phone using regex
    email_match = re.search(r"[\w\.-]+@[\w\.-]+", text)
    if email_match:
        email = email_match.group(0)
    phone_match = re.search(r"\b\+?\d{10,15}\b", text)
    if phone_match:
        phone = phone_match.group(0)

    # Extract name: assume the first PERSON entity is the candidate name
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            name = ent.text
            break

    # Extract organizations as education/work experience heuristically
    for ent in doc.ents:
        if ent.label_ == "ORG":
            education.append(ent.text)

    # Keyword search for skills (case insensitive)
    lower_text = text.lower()
    for skill in SKILL_KEYWORDS:
        if skill in lower_text:
            skills.append(skill)

    # Remove duplicates and clean up
    education = list(dict.fromkeys(education))
    skills = list(dict.fromkeys(skills))

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "education": education,
        "experience": experience,
        "skills": skills,
    }