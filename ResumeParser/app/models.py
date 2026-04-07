from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

# ---- ObjectId support for Pydantic ----
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, *args, **kwargs):
        return {"type": "string"}

# ---- Nested models ----
class ResumeData(BaseModel):
    summary: Optional[str] = None
    experience: Optional[str] = None
    education: List[str] = []
    projects: List[str] = []
    skills: List[str] = []
    certifications: List[str] = []

class PsychometricResult(BaseModel):
    personality_type: Optional[str] = None
    aptitude_score: Optional[int] = None
    test_date: Optional[datetime] = None

# ---- Main user profile ----
class UserProfile(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    resume: Optional[ResumeData] = None
    psychometric: Optional[PsychometricResult] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str, PyObjectId: str, datetime: lambda v: v.isoformat()}
