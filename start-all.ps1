# start.ps1
# =========
# Start the Atlas Alpha API server with all required environment variables.
# Run from the Quant-Signal-Platform root or anywhere.
#
# Usage:
#   .\start.ps1              # start server (default port 8080)
#   .\start.ps1 -Port 3000   # custom port
#   .\start.ps1 -Build       # force rebuild before start
#   .\start.ps1 -Dev         # build + start (same as pnpm run dev)

param(
    [int]$Port = 8080,
    [switch]$Build,
    [switch]$Dev
)

$SERVER_DIR = "C:\Users\napan\OneDrive\Documents\Replit\Quant-Signal-Platform\artifacts\api-server"
$ENV_FILE   = "$SERVER_DIR\.env"

# ── Load .env ─────────────────────────────────────────────────────────────────
if (Test-Path $ENV_FILE) {
    Get-Content $ENV_FILE | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key   = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Host "  Loaded .env from $ENV_FILE" -ForegroundColor DarkGray
} else {
    Write-Host "  WARNING: .env not found at $ENV_FILE" -ForegroundColor Yellow
    Write-Host "  Setting minimum required vars..." -ForegroundColor Yellow
}

# ── Override PORT if specified ────────────────────────────────────────────────
$env:PORT = $Port

# ── Verify required vars ──────────────────────────────────────────────────────
$required = @("PORT", "DATABASE_URL")
$missing  = $required | Where-Object { -not [System.Environment]::GetEnvironmentVariable($_, "Process") }
if ($missing) {
    Write-Host "  ERROR: Missing required env vars: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "  Check $ENV_FILE" -ForegroundColor Red
    exit 1
}

# ── Display startup info ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Atlas Alpha API Server" -ForegroundColor Cyan
Write-Host "  ──────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Port:     $Port" -ForegroundColor White
Write-Host "  DB:       $($env:DATABASE_URL -replace ':([^@]+)@', ':***@')" -ForegroundColor White
if ($env:DATABASE_URL_RESEARCH) {
    Write-Host "  ResearchDB: $($env:DATABASE_URL_RESEARCH -replace ':([^@]+)@', ':***@')" -ForegroundColor White
}
Write-Host "  Dir:      $SERVER_DIR" -ForegroundColor DarkGray
Write-Host ""

# ── Kill any existing process on this port ────────────────────────────────────
$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Killing existing process on port $Port..." -ForegroundColor Yellow
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}

# ── Run ───────────────────────────────────────────────────────────────────────
Push-Location $SERVER_DIR

if ($Dev) {
    Write-Host "  Running: pnpm run dev (build + start)" -ForegroundColor Cyan
    pnpm run dev
} elseif ($Build) {
    Write-Host "  Running: pnpm run build then start" -ForegroundColor Cyan
    pnpm run build
    if ($LASTEXITCODE -eq 0) { pnpm run start }
} else {
    Write-Host "  Running: pnpm run start" -ForegroundColor Cyan
    Write-Host "  (Use -Build flag to rebuild first, -Dev for build+start)" -ForegroundColor DarkGray
    Write-Host ""
    pnpm run start
}

Pop-Location