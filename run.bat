@echo off
setlocal
set ROOT=%~dp0

if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo Python venv not found. First-time setup:
  echo   python -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo   npm --prefix frontend install
  exit /b 1
)

echo Starting backend  -^> http://127.0.0.1:8000
start "transcode-backend" "%ROOT%.venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

timeout /t 2 >nul
echo Starting frontend -^> http://localhost:5173
start "" http://localhost:5173
cmd /c npm --prefix "%ROOT%frontend" run dev
