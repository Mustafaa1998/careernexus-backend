# resume_parser/ocr.py
from __future__ import annotations
from pathlib import Path
from typing import List
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import io

from .config import TESSERACT_CMD, POPPLER_PATH, OCR_DPI, OCR_LANG, OCR_PSM, OCR_OEM

# Make sure pytesseract points at the exe on Windows
#pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
pytesseract.pytesseract.tesseract_cmd = r"D:\Program Files\Tesseract-OCR\tesseract.exe"


def image_to_text(img: Image.Image) -> str:
    # Convert to grayscale to stabilize OCR a bit
    gray = img.convert("L")
    cfg = f"--oem {OCR_OEM} --psm {OCR_PSM}"
    return pytesseract.image_to_string(gray, lang=OCR_LANG, config=cfg)

def pdf_to_text_via_ocr(pdf_path: str) -> str:
    """
    Convert each PDF page to an image via Poppler and run Tesseract.
    Returns concatenated text.
    """
    pages: List[Image.Image] = convert_from_path(
        pdf_path,
        dpi=OCR_DPI,
        poppler_path=POPPLER_PATH  # omit this arg if poppler is on PATH
    )

    parts: List[str] = []
    for i, page in enumerate(pages, 1):
        text = image_to_text(page)
        parts.append(text)
    return "\n\n".join(parts)
