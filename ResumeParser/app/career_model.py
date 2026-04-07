# app/career_model.py
from __future__ import annotations
from pathlib import Path
from typing import List

from sentence_transformers import SentenceTransformer

# Optional: allow override via env (default to CareerBERT-JG)
import os
MODEL_NAME = os.getenv("CAREER_MODEL_NAME", "lwolfrum2/careerbert-jg")

# Locate careers.txt relative to this file
HERE = Path(__file__).resolve().parent
CAREERS_PATH = HERE / "careers.txt"

if not CAREERS_PATH.exists():
    raise FileNotFoundError(f"careers.txt not found at: {CAREERS_PATH}")

# ---- Load model once (cold start will be a bit slower) ----
model: SentenceTransformer = SentenceTransformer(MODEL_NAME)

# ---- Load career labels ----
with CAREERS_PATH.open("r", encoding="utf-8") as f:
    career_titles: List[str] = [line.strip() for line in f if line.strip()]

if not career_titles:
    raise ValueError("careers.txt is empty. Add at least a few job titles.")

# ---- Precompute embeddings for labels (once) ----
# convert_to_tensor=True returns a torch.Tensor, efficient for cosine similarity
career_embeddings = model.encode(career_titles, convert_to_tensor=True)
