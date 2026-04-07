from __future__ import annotations
import os, json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat, job_proxy, uni_proxy, resume_proxy, psycho_proxy

app = FastAPI(title="CareerNexus Chatbot Gateway")

raw = os.getenv("ALLOW_ORIGINS", '["http://localhost:5173","http://localhost:3000"]')
try:
    allow_origins = json.loads(raw) if raw.strip().startswith("[") else [
        o.strip() for o in raw.split(",") if o.strip()
    ]
except Exception:
    allow_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat)
app.include_router(job_proxy)
app.include_router(uni_proxy)
app.include_router(resume_proxy)
app.include_router(psycho_proxy)
