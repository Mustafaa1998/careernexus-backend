@echo off
setlocal

REM Go to folder where this .bat lives
cd /d "%~dp0"

echo ============================================
echo  Resume Parser API - CareerNexus
echo ============================================

echo.
echo Activating virtual environment (venv)...

REM If venv doesn't exist, create it and install deps
if not exist "venv\Scripts\activate.bat" (
    echo venv not found. Creating venv...
    py -m venv venv

    echo Activating new venv...
    call venv\Scripts\activate.bat

    echo Installing requirements from requirements.txt ...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting Resume Parser API on http://127.0.0.1:8000 ...

REM ENTRYPOINT: FastAPI app is usually in app/main.py as "app"
python -m uvicorn app.main:app --reload --port 8000

echo.
echo Server stopped. Press any key to close this window.
pause
