"""
Recommendation Engine
This module defines a simple recommendation engine that matches user skills
against a database of university programs and jobs using TF‑IDF vectorization
and cosine similarity. For demonstration purposes, the data is loaded from
JSON files stored in the `data` folder.
"""

# recommendation.py (replace the RecommendEngine with this)

from __future__ import annotations
import json, os
from pathlib import Path
from typing import List
import numpy as np

try:
    # Prefer sklearn if available
    from sklearn.feature_extraction.text import TfidfVectorizer
except Exception as _:
    TfidfVectorizer = None


DATA_DIR = Path(__file__).resolve().parent / "data"
JOBS_PATH = DATA_DIR / "jobs.json"
UNIS_PATH = DATA_DIR / "universities.json"


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _text_from_row(row: dict, keys: list[str]) -> str:
    parts = []
    for k in keys:
        v = row.get(k)
        if isinstance(v, list):
            parts.extend([str(x) for x in v if x])
        elif v:
            parts.append(str(v))
    return " ".join(parts).strip()


class _TFIDF:
    """Tiny wrapper so we can keep the rest of the code clean."""
    def __init__(self, docs: List[str]):
        if TfidfVectorizer is None:
            raise RuntimeError("scikit-learn not installed")
        # Accept almost anything; do NOT remove stop words here
        self.v = TfidfVectorizer(
            min_df=1,
            max_df=1.0,
            lowercase=True,
            token_pattern=r"(?u)\b[\w\-\+#\.]+\b",
            stop_words=None,
        )
        # Guard: if everything is empty, raise a helpful error
        docs = [d if isinstance(d, str) else "" for d in docs]
        if not any(d.strip() for d in docs):
            raise ValueError("All documents are empty. Check your JSON fields.")
        self.m = self.v.fit_transform(docs)

    def query(self, q: str, top_k: int) -> List[int]:
        if not q.strip():
            # Empty query → return “top” as first K rows
            return list(range(min(top_k, self.m.shape[0])))
        qv = self.v.transform([q])
        scores = (self.m @ qv.T).toarray().ravel()  # cosine on tf-idf works as dot
        idx = np.argsort(-scores)
        return idx[:top_k].tolist()


class RecommendEngine:
    def __init__(self):
        # Load data
        self.jobs = _read_json(JOBS_PATH)
        self.unis = _read_json(UNIS_PATH)

        # Build corpora using whatever fields exist
        job_keys = ["title", "company", "skills", "location", "description", "stack"]
        uni_keys = ["university_name", "field", "program_name", "city", "province", "notes"]

        self.job_texts = [_text_from_row(r, job_keys) for r in self.jobs]
        self.uni_texts = [_text_from_row(r, uni_keys) for r in self.unis]

        # Initialize TF-IDF models
        self.job_model = _TFIDF(self.job_texts) if self.jobs else None
        self.uni_model = _TFIDF(self.uni_texts) if self.unis else None

    # ---- public APIs expected by app_fest.py ----
    def recommend_jobs(self, skills: List[str], top_k: int = 10) -> List[dict]:
        if not self.jobs or self.job_model is None:
            return []
        query = " ".join(skills or []).strip()
        idx = self.job_model.query(query, top_k)
        return [self.jobs[i] for i in idx if i < len(self.jobs)]

    def recommend_universities(self, skills: List[str], top_k: int = 10) -> List[dict]:
        if not self.unis or self.uni_model is None:
            return []
        query = " ".join(skills or []).strip()
        idx = self.uni_model.query(query, top_k)
        return [self.unis[i] for i in idx if i < len(self.unis)]
