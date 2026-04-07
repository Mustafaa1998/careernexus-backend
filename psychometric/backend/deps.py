# backend/deps.py
from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .db_pg import get_pg
from .models_pg import User
from .security import decode_token

bearer = HTTPBearer(auto_error=True)

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_pg),
) -> User:
    # Parse token
    try:
        payload = decode_token(creds.credentials)   # may raise
        sub = payload.get("sub")
        if not sub:
            raise ValueError("no sub in token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Load user
    user = db.get(User, sub)  # SQLAlchemy 2.x style
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
