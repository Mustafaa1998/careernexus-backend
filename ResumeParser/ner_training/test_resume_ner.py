import spacy
from pathlib import Path

MODEL_PATH = Path("models/resume_ner_300")

def test_model():
    if not MODEL_PATH.exists():
        print("❌ Model not found. Run train_resume_ner.py first.")
        return

    nlp = spacy.load(MODEL_PATH)
    text = """
    Hamna Farooq — Computer Science Undergraduate
    Email: punjwanihamna11@gmail.com | Phone: 0320-2449523
    Education: Bachelors of Science in Computer Science at Iqra University (2022 - Present)
    Experience: English Teacher, SAJ Academy 2021 – 2022
    Skills: Java, TypeScript, Node.js, React, PostgreSQL, Python
    """

    doc = nlp(text)
    print("\n=== Recognized Entities ===")
    for ent in doc.ents:
        print(f"{ent.text:40} -> {ent.label_}")

if __name__ == "__main__":
    test_model()
