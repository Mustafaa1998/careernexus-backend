@echo off
REM Go to backend folder
cd /d "D:\CareerNexus\CareerNexusFYP2\CareerNexus_Recommendation\backend"

echo ============================================
echo  CareerNexus Job Recommendation API - CareerNexus
echo ============================================

REM Activate the correct virtual environment
call venv\Scripts\activate.bat

REM Start the Recommendation API
uvicorn app_fest:app --reload --port 8001
