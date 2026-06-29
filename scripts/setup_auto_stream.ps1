<#
.SYNOPSIS
    Register the Alpaca auto-stream as a Windows Scheduled Task.
    Run this ONCE as Administrator to set it up.

.USAGE
    Right-click PowerShell → "Run as Administrator"
    cd C:\Atlas\atlas-research
    .\scripts\setup_auto_stream.ps1

    Optionally override paths:
    .\scripts\setup_auto_stream.ps1 -AtlasRoot "D:\MyAtlas" -Tickers "AAPL,MSFT,NVDA,TSLA"
#>
param(
    [string]$AtlasRoot   = "C:\Atlas",
    [string]$ScriptPath  = "C:\Atlas\atlas-research\scripts\alpaca_stream_auto.py",
    [string]$PythonExe   = "C:\Python314\python.exe",
    [string]$Tickers     = "",           # empty = use --universe flag
    [string]$OutDir      = "C:\Atlas\data",
    [string]$LogDir      = "C:\Atlas\data\logs",
    [string]$TaskName    = "AtlasAlphaTickStream"
)

# ── Validate ────────────────────────────────────────────────────────────────
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath  — run 'git pull' first"
    exit 1
}
if (-not (Test-Path $PythonExe)) {
    # Try py launcher
    $PythonExe = (Get-Command py -ErrorAction SilentlyContinue)?.Source
    if (-not $PythonExe) {
        Write-Error "Python not found. Set -PythonExe to your python.exe path."
        exit 1
    }
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# ── Build argument string ───────────────────────────────────────────────────
$tickerArg = if ($Tickers) { "--tickers $Tickers" } else { "--universe" }
$streamLog = "$LogDir\task_scheduler.log"
$args_str  = "`"$ScriptPath`" $tickerArg --out-dir `"$OutDir`""

# ── Wrapper batch file (captures stdout to log) ─────────────────────────────
$batchPath = "$AtlasRoot\run_stream.bat"
@"
@echo off
set ALPACA_API_KEY=%ALPACA_API_KEY%
set ALPACA_SECRET_KEY=%ALPACA_SECRET_KEY%
set ALPACA_OUT_DIR=$OutDir
set ALPACA_5M_DIR=$OutDir\5m
set GITHUB_TOKEN=%GITHUB_TOKEN%
"$PythonExe" $args_str >> "$streamLog" 2>&1
"@ | Set-Content $batchPath -Encoding ASCII

Write-Host "Batch wrapper → $batchPath"

# ── Scheduled Task ──────────────────────────────────────────────────────────
# Fires at 06:25 AM Pacific Mon–Fri (adjust if you're in another timezone)
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday `
    -At "06:25AM"

$action  = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$batchPath`""

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 12) `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Run as current user (has access to env vars)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

# Remove old task if exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger  $trigger `
    -Action   $action `
    -Settings $settings `
    -Principal $principal `
    -Description "Atlas Alpha — Alpaca tick stream, auto-starts at market open Mon-Fri" |
    Out-Null

Write-Host ""
Write-Host "✓ Scheduled Task registered: '$TaskName'"
Write-Host "  Fires:  Mon-Fri at 06:25 AM (Pacific)"
Write-Host "  Script: $ScriptPath"
Write-Host "  Log:    $streamLog"
Write-Host ""
Write-Host "IMPORTANT — set these env vars in System Properties → Environment Variables"
Write-Host "  (so the task inherits them at startup):"
Write-Host "  ALPACA_API_KEY    = <your key>"
Write-Host "  ALPACA_SECRET_KEY = <your secret>"
Write-Host "  GITHUB_TOKEN      = <optional>"
Write-Host ""
Write-Host "Test it now (won't wait for market if closed — stream exits immediately):"
Write-Host "  python `"$ScriptPath`" --universe --out-dir `"$OutDir`""
