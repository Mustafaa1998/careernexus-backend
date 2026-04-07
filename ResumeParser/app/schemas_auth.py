from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field

class RegisterUser(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str  = Field(min_length=1, max_length=80)
    contact: str    = Field(min_length=4, max_length=32)
    email: EmailStr
    password: str   = Field(min_length=6, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserPublic(BaseModel):
    id: str
    first_name: str
    last_name: str
    contact: str
    email: EmailStr

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class MeResponse(UserPublic):
    pass

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=6)

class MessageResponse(BaseModel):
    message: str