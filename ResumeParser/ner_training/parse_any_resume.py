"""
parse_any_resume.py
-------------------
Use your fine-tuned spaCy NER model to extract information
(NAME, EMAIL, PHONE, EDUCATION, SKILL, ORG, DESIGNATION, EXPERIENCE)
from any resume (PDF or DOCX).

Usage:
    python parse_any_resume.py "D:\\ResumeParser\\sample_resumes\\someone_resume.pdf"
"""
"""
parse_any_resume.py
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import spacy
from pathlib import Path
from resume_parser.parser import read_pdf_text, read_docx_text
from resume_parser.utils import get_extension


MODEL_PATH = Path("ner_training/models/resume_ner_300")

def extract_entities_from_resume(file_path: str):
    """Extracts NER entities from a given PDF or DOCX resume file."""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {path}")
        return

    ext = get_extension(path)
    if ext not in (".pdf", ".docx"):
        print("❌ Only PDF and DOCX files are supported.")
        return

    # Load fine-tuned NER model
    print("📘 Loading model...")
    nlp = spacy.load(MODEL_PATH)

    # Extract text from resume
    print(f"📄 Reading file: {path.name}")
    if ext == ".pdf":
        text = read_pdf_text(path)
    else:
        text = read_docx_text(path)

    if not text.strip():
        print("⚠️ No text found — possibly a scanned image PDF.")
        return

    # Run NER model
    print("\n🔍 Extracting entities...\n")
    doc = nlp(text)

    # Print results
    results = {}
    for ent in doc.ents:
        label = ent.label_
        value = ent.text.strip()
        results.setdefault(label, []).append(value)

    for label, values in results.items():
        print(f"{label}:")
        for v in values:
            print(f"  - {v}")
        print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_any_resume.py <path_to_resume>")
    else:
        extract_entities_from_resume(sys.argv[1])
