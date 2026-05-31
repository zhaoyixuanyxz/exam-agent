# One-click start: venv/deps -> backend API -> Vite -> browser
# Run: powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
# Shared (others on LAN/Tailscale/tunnel): .\start.ps1 -Shared
param(
    [switch]$Shared
)
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
} else {
    # Venv exists but pip install may have failed. Do not use "pip show": it prints WARNING to stderr
    # when missing, which becomes a terminating error under $ErrorActionPreference = Stop.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $Py -c "import uvicorn" 2>$null | Out-Null
    $needRepair = ($LASTEXITCODE -ne 0)
    $ErrorActionPreference = $prevEap
    if ($needRepair) {
        Write-Host "Backend venv is incomplete. Running pip install..." -ForegroundColor Yellow
        Push-Location $Backend
        & $Py -m pip install -e ".[dev]"
        Pop-Location
    }
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

$apiUrl = "http://127.0.0.1:8000/openapi.json"
$deadline = (Get-Date).AddSeconds(120)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri $apiUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    Write-Host ""
    Write-Host "ERROR: Backend did not become ready at http://127.0.0.1:8000 within 120s." -ForegroundColor Red
    Write-Host "Check the BACKEND PowerShell window for Python/traceback errors (pip install failed, port in use, etc.)." -ForegroundColor Yellow
    Write-Host "Do not start the UI until API docs load: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

$viteHost = if ($Shared) { "0.0.0.0" } else { "127.0.0.1" }
$sharedEnv = if ($Shared) { '$env:EXAM_AGENT_SHARED=''1''; ' } else { '' }
Start-Process powershell `
    -WorkingDirectory $Frontend `
    -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "${sharedEnv}npm run dev -- --host $viteHost --port 5173"

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"

Write-Host "Opened browser: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "API docs: http://127.0.0.1:8000/docs | Close the two new PowerShell windows to stop servers." -ForegroundColor Gray
if ($Shared) {
    Write-Host ""
    Write-Host "=== SHARED MODE (Plan A) ===" -ForegroundColor Cyan
    Write-Host "Frontend listens on 0.0.0.0:5173 (API still local-only on :8000, proxied by Vite)." -ForegroundColor Gray
    Write-Host "Share access with colleagues - see docs/plan-a-shared-hosting.md" -ForegroundColor Yellow
    Write-Host ""
}
