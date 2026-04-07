# scripts/smoke_test.py
import shutil, spacy, sys
print("tesseract:", shutil.which("tesseract"))
print("pdftoppm:", shutil.which("pdftoppm"))
spacy.load("en_core_web_sm")
print("spaCy model: OK")
print("✅ Environment looks good.")
