from __future__ import annotations
import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import EmailStr

from .db_pg import get_pg
from .models_pg import User, PasswordReset
from .schemas_auth import RegisterUser, LoginRequest, TokenResponse, UserPublic, MeResponse, ForgotPasswordRequest, ResetPasswordRequest, MessageResponse
from .security import hash_password, verify_password, create_access_token, decode_token, hash_reset_token
from .email_utils import send_reset_email

router = APIRouter(prefix="/auth", tags=["Auth"])
bearer = HTTPBearer(auto_error=False)

@router.post("/register", response_model=UserPublic, status_code=201)
def register(payload: RegisterUser, db: Session = Depends(get_pg)):
    if db.query(User).filter(User.email == str(payload.email).lower()).first():
        raise HTTPException(status_code=409, detail="Email already registered.")
    if db.query(User).filter(User.contact == payload.contact).first():
        raise HTTPException(status_code=409, detail="Contact already registered.")

    user = User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        contact=payload.contact.strip(),
        email = payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=f"{payload.first_name.strip()} {payload.last_name.strip()}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserPublic(
        id=str(user.id),
        first_name=user.first_name,
        last_name=user.last_name,
        contact=user.contact,
        email=user.email,
    )

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_pg)):
    email = payload.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(sub=str(user.id))
    return TokenResponse(access_token=token)

def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_pg),
) -> User:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        data = decode_token(creds.credentials)
        user_id = data.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user

@router.get("/me", response_model=MeResponse)
def me(current: User = Depends(get_current_user)):
    return MeResponse(
        id=str(current.id),
        first_name=current.first_name,
        last_name=current.last_name,
        contact=current.contact,
        email=current.email,
    )

@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_pg)):
    email = str(payload.email).lower()
    user = db.query(User).filter(User.email == email).first()

    msg = "If the email exists, a password reset link has been sent."

    if not user:
        return MessageResponse(message=msg)

    token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(token)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    pr = PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
    db.add(pr)
    db.commit()

    frontend = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    reset_link = f"{frontend}/reset-password?token={token}"

    try:
        send_reset_email(to_email=user.email, reset_link=reset_link)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")

    return MessageResponse(message=msg)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_pg)):
    token_hash = hash_reset_token(payload.token)

    pr = (
        db.query(PasswordReset)
        .filter(PasswordReset.token_hash == token_hash)
        .order_by(PasswordReset.created_at.desc())
        .first()
    )

    if not pr:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    if pr.used_at is not None:
        raise HTTPException(status_code=400, detail="Reset token already used.")
    if pr.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user = db.query(User).filter(User.id == pr.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    user.password_hash = hash_password(payload.new_password)
    pr.used_at = datetime.utcnow()

    db.add(user)
    db.add(pr)
    db.commit()

    return MessageResponse(message="Password updated successfully. Please login.")
