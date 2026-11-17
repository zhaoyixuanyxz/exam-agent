# Quick public HTTPS link for Plan A human smoke (run AFTER start-shared.bat is up).
# Requires cloudflared: winget install Cloudflare.cloudflared
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\start-cloudflare-tunnel.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Frontend = "http://127.0.0.1:5173"
$Backend = "http://127.0.0.1:8000/openapi.json"
$EnvFile = Join-Path $Root "backend\.env"

function Test-Url([string]$Url, [int]$TimeoutSec = 3) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400)
    } catch {
        return $false
    }
}

try {
    $null = Get-Command cloudflared -ErrorAction Stop
} catch {
    Write-Host "未找到 cloudflared。请先安装：" -ForegroundColor Red
    Write-Host "  winget install Cloudflare.cloudflared" -ForegroundColor Yellow
    Write-Host "装好后重新打开本脚本。" -ForegroundColor Yellow
    exit 1
}

Write-Host "cloudflared: $((Get-Command cloudflared).Source)" -ForegroundColor Gray

if (-not (Test-Path $EnvFile)) {
    Write-Host ""
    Write-Host "警告：找不到 backend\.env。冒烟时调用 DeepSeek 会失败。" -ForegroundColor Yellow
    Write-Host "  复制 .env.example 为 backend\.env，填入 DEEPSEEK_API_KEY 后再测。" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "检查本机后端 $Backend ..." -ForegroundColor Gray
if (-not (Test-Url $Backend)) {
    Write-Host "后端未就绪（:8000）。请先启动共享模式：" -ForegroundColor Red
    Write-Host "  双击 start-shared.bat" -ForegroundColor Yellow
    Write-Host "  或: powershell -ExecutionPolicy Bypass -File .\start.ps1 -Shared" -ForegroundColor Yellow
    Write-Host "等 API 文档能打开 http://127.0.0.1:8000/docs 后再跑本脚本。" -ForegroundColor Yellow
    exit 1
}
Write-Host "  后端 OK" -ForegroundColor Green

Write-Host "检查本机前端 $Frontend ..." -ForegroundColor Gray
if (-not (Test-Url $Frontend)) {
    Write-Host "前端未就绪（:5173）。共享模式应同时起 Vite。" -ForegroundColor Red
    Write-Host "  确认 start-shared.bat / start.ps1 -Shared 的两个窗口都还开着。" -ForegroundColor Yellow
    Write-Host "  本机先打开 http://127.0.0.1:5173 能进页面，再开隧道。" -ForegroundColor Yellow
    exit 1
}
Write-Host "  前端 OK" -ForegroundColor Green

Write-Host ""
Write-Host "正在启动 Cloudflare 临时隧道 -> $Frontend" -ForegroundColor Cyan
Write-Host "终端里会出现 https://xxxx.trycloudflare.com — 复制该链接做人工冒烟。" -ForegroundColor Yellow
Write-Host "保持本窗口开着；Ctrl+C 结束隧道（链接立刻失效）。电脑勿休眠。" -ForegroundColor Gray
Write-Host ""

& cloudflared tunnel --url $Frontend
