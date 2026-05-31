# Quick public HTTPS link for Plan A (run AFTER start-shared.bat is up).
# Requires cloudflared: winget install Cloudflare.cloudflared
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\start-cloudflare-tunnel.ps1
$ErrorActionPreference = "Stop"
$target = "http://127.0.0.1:5173"

try {
    $null = Get-Command cloudflared -ErrorAction Stop
} catch {
    Write-Host "cloudflared not found. Install:" -ForegroundColor Red
    Write-Host "  winget install Cloudflare.cloudflared" -ForegroundColor Yellow
    Write-Host "Then re-run this script." -ForegroundColor Yellow
    exit 1
}

Write-Host "Checking local app at $target ..." -ForegroundColor Gray
try {
    $r = Invoke-WebRequest -Uri $target -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    if ($r.StatusCode -ne 200) { throw "bad status" }
} catch {
    Write-Host "Local app not ready. Start start-shared.bat first, then run this script again." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting Cloudflare quick tunnel -> $target" -ForegroundColor Cyan
Write-Host "Copy the https://....trycloudflare.com URL and send to colleagues." -ForegroundColor Yellow
Write-Host "Keep this window open. Ctrl+C to stop the tunnel." -ForegroundColor Gray
Write-Host ""

& cloudflared tunnel --url $target
