# backend/security.py
from __future__ import annotations
import os, jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")

def decode_token(token: str) -> dict:
    """
    Decode JWT issued by ResumeParser service.
    Returns a dict with at least: {"sub": "<user_uuid>", "iat": ..., "exp": ...}
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
