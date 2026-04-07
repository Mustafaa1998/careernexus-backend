# app/models_pg.py
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
    Numeric,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .db_pg import Base  # single Base from db_pg


# -------------------------
# Users (auth + profile)
# -------------------------
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("contact", name="uq_users_contact"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name:  Mapped[str] = mapped_column(String(80), nullable=False)
    contact:    Mapped[str] = mapped_column(String(32), nullable=False)
    email:      Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


# -------------------------
# Personality results (psychometric)
# -------------------------
class PersonalityResult(Base):
    __tablename__ = "personality_results"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # legacy optional email
    user_identifier = Column(String, nullable=True)

    total_questions = Column(Integer, nullable=True)
    answered = Column(Integer, nullable=True)
    scores = Column(JSON, nullable=True)
    dominant = Column(String(100), nullable=True)
    summary = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_personality_results_user_id_created_at", "user_id", "created_at"),
    )


# -------------------------
# Aptitude results
# -------------------------
class AptitudeResult(Base):
    __tablename__ = "aptitude_results"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    domain = Column(String(64), nullable=True)
    level  = Column(String(64), nullable=True)

    total   = Column(Integer, nullable=False)
    correct = Column(Integer, nullable=False)
    percent = Column(Numeric(5, 2), nullable=False)  # store as numeric
    breakdown = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_aptitude_results_user_id_created_at", "user_id", "created_at"),
    )

class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)