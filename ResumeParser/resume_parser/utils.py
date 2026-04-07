# resume_parser/utils.py
from __future__ import annotations
import os
import logging
import mimetypes
import re
from typing import Literal

from .config import LOG_LEVEL

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("resume_parser.utils")

SupportedExt = Literal[".pdf", ".docx"]

def get_extension(path: str) -> SupportedExt:
    ext = os.path.splitext(path)[-1].lower()
    if ext not in (".pdf", ".docx"):
        raise ValueError(f"Unsupported file type: {ext}. Allowed: .pdf, .docx")
    return ext  # type: ignore[return-value]

def guess_mime(path: str) -> str | None:
    return mimetypes.guess_type(path)[0]

def clean_whitespace(text: str) -> str:
    # Normalize whitespace, keep meaningful line breaks
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def safe_slice_lines(text: str, max_chars: int = 2000) -> str:
    """Short preview for logs."""
    t = text.replace("\n", " ")[:max_chars]
    return (t + "...") if len(text) > max_chars else t
