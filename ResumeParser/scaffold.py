import os
files = [
    "README.md","requirements.txt",".gitignore",".env.example",
    "sample_resumes/sample_resume_selectable.pdf",
    "sample_resumes/sample_resume_scanned.pdf",
    "sample_resumes/sample_resume.docx",
    "scripts/smoke_test.py","scripts/download_spacy_model.bat","scripts/download_spacy_model.sh",
    "app/__init__.py","app/api.py","app/main.py",
    "resume_parser/__init__.py","resume_parser/config.py","resume_parser/utils.py",
    "resume_parser/preprocessing.py","resume_parser/ocr.py","resume_parser/nlp.py",
    "resume_parser/patterns.py","resume_parser/extractors.py","resume_parser/parser.py",
    "resume_parser/schema.py",
    "resume_parser/resources/skills.json","resume_parser/resources/degree_keywords.csv",
    "resume_parser/resources/location_gazetteer.txt","resume_parser/resources/stopwords.txt",
    "tests/__init__.py","tests/test_utils.py","tests/test_preprocessing.py",
    "tests/test_extractors.py","tests/test_parser_integration.py","tests/test_api.py",
]
for f in files:
    os.makedirs(os.path.dirname(f) or ".", exist_ok=True)
    if not os.path.exists(f):
        open(f, "a", encoding="utf-8").close()
print("✅ Scaffolding complete.")
