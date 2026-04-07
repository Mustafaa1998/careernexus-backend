@echo off
setlocal

REM Go to the folder where this .bat file is located
cd /d "%~dp0"

echo ============================================
echo  Psychometric API - CareerNexus
echo ============================================

echo.
echo Activating virtual environment (venv)...

REM If venv doesn't exist, create it and install dependencies
if not exist "venv\Scripts\activate.bat" (
    echo venv not found. Creating venv...
    py -m venv venv

    echo Activating new venv...
    call venv\Scripts\activate.bat

    echo Installing requirements from backend\requirements.txt ...
    python -m pip install --upgrade pip
    python -m pip install -r backend\requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting Psychometric API on http://127.0.0.1:8003 ...
cd backend

REM If your FastAPI instance is named "app" in app.py, this is correct:
python -m uvicorn app:app --reload --port 8003

echo.
echo Server stopped. Press any key to close this window.
pause
