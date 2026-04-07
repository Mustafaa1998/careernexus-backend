@echo off
echo ==========================================
echo   STARTING ALL CAREERNEXUS BACKEND SERVICES
echo ==========================================
echo.

REM -------- Resume Parser (8000) ----------
START "ResumeParser" cmd /k "cd /d D:\CareerNexus\CareerNexusFYP2\ResumeParser & call run_resume.bat"

REM -------- Psychometric (8003) ----------
START "Psychometric" cmd /k "cd /d D:\CareerNexus\CareerNexusFYP2\psychometric & call run_psychometric.bat"

REM -------- Job Recommendation ----------
START "JobRecommendation" cmd /k "cd /d D:\CareerNexus\CareerNexusFYP2\CareerNexus_Recommendation\backend & call run_job.bat"

REM -------- Uni Recommendation ----------
START "UniRecommendation" cmd /k "cd /d D:\CareerNexus\CareerNexusFYP2\CareerNexus_Recommendation\backend\uni_rec & call run_unirec.bat"

REM -------- Chatbot (9000) ---------------
START "Chatbot" cmd /k "cd /d D:\CareerNexus\CareerNexusFYP2\CareerNexus_Chatbot\Chatbot & call run_chatbot.bat"

echo.
echo All start commands sent. Check the opened windows for logs.
pause
