# tools/test_model_on_file.py
# Test your trained spaCy resume NER model on any resume (PDF or DOCX)

import sys, spacy, pathlib

# --- make sure Python can find "resume_parser" ---
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# now import your parser helpers
from resume_parser.parser import read_pdf_text, read_docx_text

MODEL_DIR = ROOT / "ner_training" / "models" / "resume_md_best"

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools\\test_model_on_file.py <path_to_resume>")
        sys.exit(1)

    file_path = pathlib.Path(sys.argv[1])
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    # 1️⃣ Load trained model
    print("📘 Loading model:", MODEL_DIR)
    nlp = spacy.load(MODEL_DIR)

    # 2️⃣ Read text from resume
    if file_path.suffix.lower() == ".pdf":
        text = read_pdf_text(str(file_path))
    elif file_path.suffix.lower() == ".docx":
        text = read_docx_text(str(file_path))
    else:
        print("⚠️ Unsupported file type. Use PDF or DOCX.")
        sys.exit(1)

    print(f"\n📄 Parsed {len(text)} characters from {file_path.name}")

    # 3️⃣ Run model
    doc = nlp(text)

    # 4️⃣ Display entities
    print("\n=== Recognized Entities ===")
    for ent in doc.ents:
        print(f"{ent.text.strip():40s} -> {ent.label_}")

if __name__ == "__main__":
    main()
