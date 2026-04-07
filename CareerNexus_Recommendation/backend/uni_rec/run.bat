@echo off
cd /d "%~dp0"
if not exist .venv (
  "C:\Users\stm\AppData\Local\Programs\Python\Python312\python.exe" -m venv .venv

)
call .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
uvicorn app:app --reload --port 8100
