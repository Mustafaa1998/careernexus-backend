"""
Recommendation Engine
This module defines a simple recommendation engine that matches user skills
against a database of university programs and jobs using TF‑IDF vectorization
and cosine similarity. For demonstration purposes, the data is loaded from
JSON files stored in the `data` folder.
"""

import json
import os
from typing import List, Dict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _load_data(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class RecommendEngine:
    def __init__(self):
        # Load datasets
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.universities = _load_data(os.path.join(base_dir, "data", "universities.json"))
        self.jobs = _load_data(os.path.join(base_dir, "data", "jobs.json"))
        # Precompute TF‑IDF matrix for universities and jobs
        self.uni_vectorizer, self.uni_matrix = self._build_matrix(self.universities)
        self.job_vectorizer, self.job_matrix = self._build_matrix(self.jobs)

    def _build_matrix(self, items: List[Dict]):
        corpus = []
        for item in items:
            # Combine description and skills into one string
            text = item.get("description", "") + " " + " ".join(item.get("skills", []))
            corpus.append(text)
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(corpus)
        return vectorizer, matrix

    def _recommend(self, query_skills: List[str], vectorizer, matrix, items: List[Dict], top_n: int = 3) -> List[Dict]:
        # Create query string from skills
        query_str = " ".join(query_skills)
        q_vec = vectorizer.transform([query_str])
        sims = cosine_similarity(q_vec, matrix)[0]
        # Get indices of top results
        top_indices = sims.argsort()[::-1][:top_n]
        recommendations = []
        for idx in top_indices:
            item = items[idx].copy()
            item["score"] = float(sims[idx])
            recommendations.append(item)
        return recommendations

    def recommend_universities(self, skills: List[str], top_n: int = 3) -> List[Dict]:
        return self._recommend(skills, self.uni_vectorizer, self.uni_matrix, self.universities, top_n)

    def recommend_jobs(self, skills: List[str], top_n: int = 3) -> List[Dict]:
        return self._recommend(skills, self.job_vectorizer, self.job_matrix, self.jobs, top_n)