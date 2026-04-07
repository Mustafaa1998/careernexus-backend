@echo off

cd /d "D:\CareerNexus\CareerNexusFYP2\CareerNexus_Chatbot\Chatbot"

call .venv\Scripts\activate

echo ================================
echo       STARTING CHATBOT API
echo ================================

uvicorn app.main:app --reload --port 9000

pause
