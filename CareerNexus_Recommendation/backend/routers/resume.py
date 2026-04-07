from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pathlib import Path
from typing import Optional, Dict, Any, List
import re, io

router = APIRouter(prefix="/resume", tags=["resume"])

try:
    import pdfplumber
except Exception:
    pdfplumber = None

VOCAB_PATH = Path(__file__).resolve().parent.parent / "data" / "skills_vocab.txt"
if not VOCAB_PATH.exists():
    VOCAB_PATH.write_text("\n".join([
        "python","django","flask","fastapi","react","next.js","javascript","typescript",
        "node.js","express","java","spring","c#",".net","php","laravel","sql","postgresql",
        "mysql","mongodb","docker","kubernetes","aws","azure","gcp","git","linux","html",
        "css","tailwind","redux","rest","graphql","ml","nlp","pandas","numpy",
        "scikit-learn","tensorflow","pytorch","devops","ci/cd","power bi","tableau"
    ]), encoding="utf-8")

def load_vocab() -> List[str]:
    return [x.strip() for x in VOCAB_PATH.read_text(encoding="utf-8").splitlines() if x.strip()]

def extract_skills(text: str, vocab: List[str]) -> List[str]:
    s = " " + re.sub(r"\s+"," ", text.lower()) + " "
    found=[]; seen=set()
    for term in sorted(vocab, key=len, reverse=True):
        needle = " " + term.lower() + " "
        if needle in s and term.lower() not in seen:
            seen.add(term.lower()); found.append(term)
    return found[:60]

@router.post("/extract")
async def extract(file: Optional[UploadFile]=File(None), text: Optional[str]=Form(None)) -> Dict[str, Any]:
    if not file and not text:
        raise HTTPException(400, "Provide a PDF file or text")
    content = ""
    if file:
        if not file.filename.lower().endswith(".pdf"): raise HTTPException(415, "PDF only")
        if not pdfplumber: raise HTTPException(500, "pdfplumber not installed")
        try:
            with pdfplumber.open(io.BytesIO(await file.read())) as pdf:
                for p in pdf.pages: content += p.extract_text() or ""
        except Exception as e:
            raise HTTPException(400, f"Could not read PDF: {e}")
    if text: content += "\n" + text
    skills = extract_skills(content, load_vocab())
    return {"count": len(skills), "skills": skills}
