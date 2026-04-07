# database.py
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load .env that sits right next to this file
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Put it in .env next to database.py")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
# --------------------------------------------------------------------------
# Optional helper to auto-create DB if it doesn't exist
# --------------------------------------------------------------------------
import re
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def ensure_database_exists(db_url: str):
    """If the target PostgreSQL database does not exist, create it."""
    # convert to psycopg2 compatible URI
    clean = db_url.replace("postgresql+psycopg2://", "postgresql://")

    # extract connection info
    m = re.match(r"^postgresql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^/?#]+)", clean)
    if not m:
        print("❌ Invalid DATABASE_URL format.")
        return
    user, pwd, host, port, dbname = m.groups()
    port = port or "5432"

    # connect to postgres default DB
    conn = psycopg2.connect(
        dbname="postgres", user=user, password=pwd, host=host, port=port
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s;", (dbname,))
    exists = cur.fetchone() is not None

    if not exists:
        print(f"🟦 Creating database '{dbname}' …")
        cur.execute(f'CREATE DATABASE "{dbname}";')
        print("✅ Database created.")
    else:
        print(f"✅ Database '{dbname}' already exists.")

    cur.close()
    conn.close()
