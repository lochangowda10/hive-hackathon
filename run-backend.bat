@echo off
REM SwingLens backend launcher - no venv activation needed.
REM Do NOT redirect this script's output; uvicorn's logger needs a console.
cd /d "%~dp0backend"
".\venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
pause
