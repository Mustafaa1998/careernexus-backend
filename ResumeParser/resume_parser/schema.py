# resume_parser/schema.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List

class EducationItem(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[int] = None

class ExperienceItem(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    date_range: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None

class ParseResponse(BaseModel):
    filename: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    summary: Optional[str] = None

    education: List[EducationItem] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    years: List[int] = Field(default_factory=list)

    raw_text: Optional[str] = None
