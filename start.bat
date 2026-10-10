@echo off
rem Starts the Vid2Post backend and frontend, then opens the app.
cd /d "%~dp0"
start "Vid2Post backend" cmd /k "cd backend && .venv\Scripts\python -m uvicorn app.main:app --reload --reload-dir app --port 8000"
start "Vid2Post frontend" cmd /k "cd frontend && npm run dev"
timeout /t 8 /nobreak >nul
start "" http://localhost:5173
