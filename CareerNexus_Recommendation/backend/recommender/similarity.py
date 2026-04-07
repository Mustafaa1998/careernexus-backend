from typing import List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def text_cosine(query_terms: List[str], doc_parts: List[str]) -> float:
    q = " ".join(t.strip().lower() for t in query_terms if t)
    d = " ".join(p.strip().lower() for p in doc_parts if p)
    if not q or not d:
        return 0.0
    vec = TfidfVectorizer(min_df=1, stop_words="english")
    X = vec.fit_transform([q, d])
    return float(cosine_similarity(X[0], X[1])[0, 0])
