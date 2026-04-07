# models.py
from __future__ import annotations
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class University(Base):
    __tablename__ = "universities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # CSV columns (mapped)
    university_id = Column(String(64), index=True, nullable=True)   # your CSV id if present
    university_name = Column(String(256), index=True, nullable=False)
    province = Column(String(128), nullable=True)
    city = Column(String(128), index=True, nullable=True)
    type = Column(String(64), nullable=True)  # public/private
    specialization = Column(String(512), nullable=True)  # text like "engineering, IT..."
    programs_offered = Column(String(1024), nullable=True)
    eligibility_criteria = Column(String(1024), nullable=True)
    fee_range_year_min = Column(Float, nullable=True)
    fee_range_year_max = Column(Float, nullable=True)
    application_window = Column(String(256), nullable=True)
    apply_url = Column(String(512), nullable=True)
    website = Column(String(512), nullable=True)
    ranking_tier = Column(String(8), nullable=True)  # "A","B","C" etc.

    # normalized helpers we may add later
    univ_key = Column(String(256), index=True, nullable=True)
    city_norm = Column(String(128), index=True, nullable=True)

    # optional FEST flag (we’ll fill it during merge, step 2)
    offers_fest = Column(Boolean, nullable=True)

    programs = relationship("Program", back_populates="university", cascade="all, delete-orphan")


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # CSV columns (mapped)
    program_id = Column(String(64), index=True, nullable=True)
    university_id_csv = Column(String(64), index=True, nullable=True)  # original CSV linkage (kept for traceability)
    university_name = Column(String(256), index=True, nullable=False)

    province = Column(String(128), nullable=True)
    city = Column(String(128), index=True, nullable=True)
    program_name = Column(String(256), index=True, nullable=False)
    degree_level = Column(String(64), index=True, nullable=True)      # BS/MS/PhD/BE/etc
    field_category = Column(String(128), index=True, nullable=True)   # engineering, cs, business admin, etc
    duration_years = Column(Float, nullable=True)
    eligibility = Column(String(1024), nullable=True)
    fee_per_year = Column(Float, nullable=True)
    semester_fee = Column(Integer, nullable=True) 
    required_traits = Column(String(512), nullable=True)
    apply_url = Column(String(512), nullable=True)

    # derived/normalized we’ll fill in step 2 merge
    program_norm = Column(String(128), index=True, nullable=True)
    field_norm = Column(String(128), index=True, nullable=True)
    level_norm = Column(String(64), index=True, nullable=True)

    # DB foreign key to canonical University row
    university_fk = Column(Integer, ForeignKey("universities.id", ondelete="CASCADE"), nullable=True)
    university = relationship("University", back_populates="programs")
