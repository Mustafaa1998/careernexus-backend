"""
Central configuration for the Resume Parser.
Includes OCR (Tesseract + Poppler), heuristic thresholds, and global constants.
"""

import os
import shutil
from pathlib import Path

# ========== OCR CONFIGURATION ==========
# ✅ Allow turning OCR on/off via env (Render)
OCR_ENABLED: bool = os.getenv("OCR_ENABLED", "true").lower() == "true"

OCR_DPI: int = int(os.getenv("OCR_DPI", "600"))
OCR_LANG: str = os.getenv("OCR_LANG", "eng")  # e.g. "eng+urd"

# ✅ Cross-platform detection:
# - Windows: you can set TESSERACT_CMD / POPPLER_PATH in .env
# - Docker/Linux: tesseract/poppler-utils installed, auto-detect from PATH
TESSERACT_CMD: str = os.getenv(
    "TESSERACT_CMD", r"D:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Path to Poppler binaries (for pdf2image to extract images from PDFs)
POPPLER_PATH: str | None = os.getenv(
    "POPPLER_PATH", r"C:\poppler-25.12.0\Library\bin"
)

# Auto-detect for Docker/Linux if not provided
if OCR_ENABLED:
    if not TESSERACT_CMD:
        detected = shutil.which("tesseract")
        if detected:
            TESSERACT_CMD = detected

    # Poppler: pdf2image works if pdftoppm exists in PATH
    # (In Dockerfile we install poppler-utils)
    if POPPLER_PATH is None:
        pdftoppm = shutil.which("pdftoppm")
        # If pdftoppm is found, keep POPPLER_PATH=None (pdf2image will use PATH)
        # If not found, we leave it None and let runtime OCR step handle error gracefully.

# OCR tuning
OCR_PSM: int = int(os.getenv("OCR_PSM", "6"))
OCR_OEM: int = int(os.getenv("OCR_OEM", "1"))

MAX_PAGES_OCR: int = int(os.getenv("MAX_PAGES_OCR", "10"))

# ========== TEXT EXTRACTION HEURISTICS ==========
MIN_SELECTABLE_TEXT_CHARS: int = int(os.getenv("MIN_SELECTABLE_TEXT_CHARS", "500"))

# ========== SKILLS MATCHING ==========
MIN_SKILL_SIMILARITY: int = int(os.getenv("MIN_SKILL_SIMILARITY", "85"))

# ========== DATE RANGE FILTER ==========
MIN_YEAR: int = int(os.getenv("MIN_YEAR", "1970"))
MAX_YEAR: int = int(os.getenv("MAX_YEAR", "2100"))

# ========== LOGGING ==========
LOG_LEVEL: str = os.getenv("RP_LOG_LEVEL", "INFO")

# ========== PATH HELPERS ==========
BASE_DIR = Path(__file__).resolve().parents[1]
RESOURCES_DIR = BASE_DIR / "resume_parser" / "resources"

# ========== OPTIONAL WARNINGS (NO CRASH) ==========
if OCR_ENABLED:
    if not TESSERACT_CMD:
        print("⚠️  OCR enabled but Tesseract not detected. Set TESSERACT_CMD or install tesseract.")
    else:
        # Only check file exists if it's a path; detected PATH is fine
        if (":" in TESSERACT_CMD or TESSERACT_CMD.startswith(("/", "\\"))) and not Path(TESSERACT_CMD).exists():
            print(f"⚠️  Warning: Tesseract path not found: {TESSERACT_CMD}")

    if POPPLER_PATH:
        if not Path(POPPLER_PATH).exists():
            print(f"⚠️  Warning: Poppler path not found: {POPPLER_PATH}")
    else:
        # PATH-based check
        if not shutil.which("pdftoppm"):
            print("⚠️  OCR enabled but Poppler (pdftoppm) not detected. Install poppler-utils or set POPPLER_PATH.")
