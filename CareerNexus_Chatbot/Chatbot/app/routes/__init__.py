# app/routes/__init__.py
from .chat import router as chat
from .job_proxy import router as job_proxy
from .uni_proxy import router as uni_proxy
from .resume_proxy import router as resume_proxy
from .psycho_proxy import router as psycho_proxy

__all__ = [
    "chat",
    "job_proxy",
    "uni_proxy",
    "resume_proxy",
    "psycho_proxy",
]
