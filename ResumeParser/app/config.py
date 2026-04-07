# app/config.py
import os
from pydantic import BaseSettings


class Settings(BaseSettings):
    # Existing DB / Mongo vars can also live here if you want later
    JOB_REC_BASE: str = os.getenv("JOB_REC_BASE", "http://127.0.0.1:8001")
    UNI_REC_BASE: str = os.getenv("UNI_REC_BASE", "http://127.0.0.1:8002")

    class Config:
        env_file = ".env"

settings = Settings()
