# 自动化检查：ruff + pytest + 前端 build。在项目根 exam-agent 下执行：
#   powershell -ExecutionPolicy Bypass -File .\scripts\run-checks.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Backend: ruff" -ForegroundColor Cyan
Push-Location (Join-Path $Root "backend")
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "未找到 backend\.venv，正在创建并安装依赖..." -ForegroundColor Yellow
    python -m venv .venv
    & .\.venv\Scripts\pip.exe install -e ".[dev]"
}
& .\.venv\Scripts\ruff.exe check app tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& .\.venv\Scripts\python.exe -m pytest tests -q --tb=short
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location

Write-Host "==> Frontend: npm run build" -ForegroundColor Cyan
Push-Location (Join-Path $Root "frontend")
if (-not (Test-Path ".\node_modules")) {
    npm install
}
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location

Write-Host "==> 全部检查通过" -ForegroundColor Green
