# Transcode Detector launcher (dev mode: backend + frontend with hot reload).
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $py)) {
  Write-Host 'Python venv not found. First-time setup:' -ForegroundColor Yellow
  Write-Host '  python -m venv .venv'
  Write-Host '  .\.venv\Scripts\python.exe -m pip install -r requirements.txt'
  Write-Host '  npm --prefix frontend install'
  exit 1
}

Write-Host 'Starting backend  -> http://127.0.0.1:8000' -ForegroundColor Cyan
Start-Process -FilePath $py -ArgumentList '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory $root

Start-Sleep -Seconds 2
Write-Host 'Starting frontend -> http://localhost:5173' -ForegroundColor Cyan
Start-Process 'http://localhost:5173'
& npm --prefix (Join-Path $root 'frontend') run dev
