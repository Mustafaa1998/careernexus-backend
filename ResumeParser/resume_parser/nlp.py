# resume_parser/nlp.py
from __future__ import annotations
import spacy
from functools import lru_cache
import spacy
from pathlib import Path


@lru_cache(maxsize=1)
def get_nlp():
    """
    Load spaCy once (small English model for CPU).
    """
    return spacy.load("en_core_web_sm")


MODEL_PATH = Path(__file__).parent.parent / "ner_training" / "models" / "resume_ner_300"

def get_custom_ner():
    return spacy.load(MODEL_PATH)

# Example usage:
# nlp = get_custom_ner()
# doc = nlp(resume_text)
# for ent in doc.ents:
#     print(ent.text, ent.label_)

