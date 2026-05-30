# One-time setup for the Transcode Detector (Windows).
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'python not found on PATH' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'npm not found on PATH' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host 'WARNING: ffmpeg not found on PATH. Install it: winget install Gyan.FFmpeg' -ForegroundColor Yellow
}

Write-Host 'Creating Python venv + installing backend deps...' -ForegroundColor Cyan
python -m venv (Join-Path $root '.venv')
$py = Join-Path $root '.venv\Scripts\python.exe'
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $root 'requirements.txt')

Write-Host 'Installing frontend deps...' -ForegroundColor Cyan
& npm --prefix (Join-Path $root 'frontend') install

Write-Host ''
Write-Host 'Setup complete. Start the app with:  .\run.ps1' -ForegroundColor Green
