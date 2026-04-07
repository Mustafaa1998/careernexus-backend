# backend/models_pg.py
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .db_pg import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(80), nullable=True)
    last_name  = Column(String(80), nullable=True)
    contact    = Column(String(32), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.email}>"

class PersonalityResult(Base):
    __tablename__ = "personality_results"

    id = Column(Integer, primary_key=True)

    # canonical link to the logged-in user
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user = relationship("User")

    total_questions = Column(Integer, nullable=True)
    answered = Column(Integer, nullable=True)
    scores = Column(JSON, nullable=True)       # {"Openness": 83, ...} or BigFive/MBTI map
    dominant = Column(String(100), nullable=True)
    summary = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<PersonalityResult id={self.id} user_id={self.user_id}>"
