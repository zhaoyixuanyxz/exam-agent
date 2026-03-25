# One-click start: venv/deps -> backend API -> Vite -> browser
# Run: powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    Write-Host "Creating Python venv and installing backend deps..." -ForegroundColor Yellow
    Push-Location $Backend
    python -m venv .venv
    & .\.venv\Scripts\pip.exe install -e ".[dev]"
    Pop-Location
}

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "Running npm install in frontend..." -ForegroundColor Yellow
    Push-Location $Frontend
    npm install
    Pop-Location
}

$envFile = Join-Path $Backend ".env"
if (-not (Test-Path $envFile)) {
    $example = Join-Path $Root ".env.example"
    if (Test-Path $example) {
        Copy-Item $example $envFile
        Write-Host "Created backend\.env from .env.example - set DEEPSEEK_API_KEY inside." -ForegroundColor Yellow
    } else {
        Write-Host "Create backend\.env with DEEPSEEK_API_KEY or the agent will fail to call the model." -ForegroundColor Yellow
    }
}

# Use -WorkingDirectory + relative commands so paths with non-ASCII (e.g. Chinese) are not embedded in -Command (avoids encoding/garbled path issues).
Start-Process powershell `
    -WorkingDirectory $Backend `
    -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

Start-Sleep -Seconds 3

Start-Process powershell `
    -WorkingDirectory $Frontend `
    -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "npm run dev -- --host 127.0.0.1 --port 5173"

Start-Sleep -Seconds 5
Start-Process "http://127.0.0.1:5173"

Write-Host "Opened browser: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "API docs: http://127.0.0.1:8000/docs | Close the two new PowerShell windows to stop servers." -ForegroundColor Gray
