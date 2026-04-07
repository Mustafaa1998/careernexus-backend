# backend/db_pg.py
from __future__ import annotations
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL=postgresql+psycopg2://postgres:123456789@127.0.0.1:5432/careernexus")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_pg():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
