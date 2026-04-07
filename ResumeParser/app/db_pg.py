# app/db_pg.py
from __future__ import annotations
import os
from dotenv import load_dotenv 
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


load_dotenv() 

# same Postgres database your psychometric/backend uses
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:@localhost:5432/careernexus"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

Base = declarative_base()  # <-- SINGLE Base for all PG models

def get_pg():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
