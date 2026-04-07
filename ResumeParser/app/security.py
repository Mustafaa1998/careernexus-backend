from __future__ import annotations

import os
import time
import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import hashlib, os
# Load .env so JWT_* values work without exporting env vars
load_dotenv()

# ===== JWT settings =====
JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
ACCESS_TOKEN_EXPIRES_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRES_MINUTES", "120"))

# Use PBKDF2-SHA256 instead of bcrypt to avoid backend/version issues.
# This uses only hashlib (no C bcrypt library), so it's very stable.
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def hash_password(raw: str) -> str:
    """Return a salted hash for storage."""
    if raw is None:
        raw = ""
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    """Verify a raw password against stored hash."""
    if raw is None:
        raw = ""
    return pwd_context.verify(raw, hashed)


def create_access_token(sub: str | int, extra: dict | None = None) -> str:
    """
    Create a signed JWT access token.
    sub: user id (string or int)
    extra: optional extra claims (merged into payload)
    """
    now = int(time.time())
    exp = now + ACCESS_TOKEN_EXPIRES_MINUTES * 60
    payload = {"sub": str(sub), "iat": now, "exp": exp, "typ": "access"}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT; raises if invalid/expired."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])


__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "JWT_SECRET",
    "JWT_ALG",
    "ACCESS_TOKEN_EXPIRES_MINUTES",
]

def hash_reset_token(token: str) -> str:
    pepper = os.getenv("RESET_TOKEN_PEPPER", "change-me").encode("utf-8")
    return hashlib.sha256(pepper + token.encode("utf-8")).hexdigest()
