# backend/models.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from db import Base


class User(Base):
    """
    Canonical identity for a person. One row per unique email.
    New psychometric results link to users.id via user_id.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Reverse relationship to results
    results = relationship("PersonalityResult", back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class PersonalityResult(Base):
    """
    Your existing table, augmented with user_id (FK to users.id).
    Keeps user_identifier (legacy email/session tag) so old code still works.
    """
    __tablename__ = "personality_results"

    id = Column(Integer, primary_key=True, index=True)
    user_identifier = Column(String, nullable=True)  # legacy: email/session tag
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    total_questions = Column(Integer, nullable=False)
    answered = Column(Integer, nullable=False)
    scores = Column(JSON, nullable=False)            # {"Openness":83,...}
    dominant = Column(String, nullable=False)        # "Openness"
    summary = Column(String, nullable=True)          # "Dominant trait: Openness. Approx MBTI: INTJ"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to User
    user = relationship("User", back_populates="results")

    def __repr__(self) -> str:
        return f"<PersonalityResult id={self.id} user_id={self.user_id}>"
