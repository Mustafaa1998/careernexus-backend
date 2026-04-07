import sys
import pathlib
import re

# Add the root directory to the sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Now you can import resume_parser.ocr
from resume_parser.ocr import pdf_to_text_via_ocr

# Function to clean the OCR text
def clean_ocr_text(text: str) -> str:
    """Clean OCR text by removing unnecessary spaces and line breaks, ensuring proper section separation."""
    
    # Remove excessive spaces and replace them with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading and trailing whitespaces
    text = text.strip()

    text = re.sub(r'[^\x00-\x7F]+', '', text)  # Remove non-ASCII characters like "i (“lOO UU (S50"

    # Add space after section headings (e.g., "EXPERIENCE", "EDUCATION", etc.)
    headings = ['SUMMARY', 'EXPERIENCE', 'EDUCATION', 'PROJECTS', 'SKILLS', 'CERTIFICATIONS', 'AWARDS', 'PUBLICATIONS']
    
    for heading in headings:
        # Match heading (case-insensitive) and add newline *before* and *after*
        text = re.sub(
            rf'(?i)(?<!\n){heading}(?!\n)',
            f'\n{heading}\n\n',
            text
        )

    # Fix common OCR issues with formatting
    text = re.sub(r'(\n\s*\n)', '\n', text)  # Remove any extra empty lines (redundant line breaks)

    return text

if len(sys.argv) < 2:
    print("Usage: python tools\\ocr_smoke_test.py <path_to_pdf>")
    sys.exit(1)

# Get the file path from arguments
pdf = pathlib.Path(sys.argv[1])

# Get text from OCR using Tesseract
text = pdf_to_text_via_ocr(str(pdf))

# Clean the OCR text to improve readability
cleaned_text = clean_ocr_text(text)

# Print the results for inspection
print(f"Chars: {len(cleaned_text)}")
print(cleaned_text[:3000])  # Print the first 3000 characters for inspection
