@echo off
REM Go to backend root (one level above uni_rec)
cd /d "D:\CareerNexus\CareerNexusFYP2\CareerNexus_Recommendation\backend"

echo ============================================
echo  CareerNexus University Recommendation API - CareerNexus
echo ============================================

REM Activate the shared virtual environment
call venv\Scripts\activate

REM Run the uni_rec FastAPI app as a PACKAGE
uvicorn uni_rec.app:app --reload --port 8002

pause

