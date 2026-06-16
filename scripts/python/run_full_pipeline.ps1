# Atlas Behavior Analysis - Full Pipeline Runner
# ================================================
# Runs all 4 steps in order from the atlas-research root directory.
#
# Usage (from atlas-research root):
#   .\scripts\python\run_full_pipeline.ps1
#   .\scripts\python\run_full_pipeline.ps1 -Tickers "SPY QQQ AAPL TSLA NVDA" -Days 30
#   .\scripts\python\run_full_pipeline.ps1 -Days 90 -MinSamples 10

param(
    [string]$Tickers     = "",
    [int]$Days           = 30,
    [int]$MinSamples     = 5,
    [string]$Python      = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Atlas Behavior Analysis Pipeline ===" -ForegroundColor Cyan
Write-Host "Days: $Days  MinSamples: $MinSamples"
Write-Host ""

# Step 1: Seed behavior definitions
Write-Host "[1/4] Seeding behavior definitions..." -ForegroundColor Yellow
& $Python scripts\python\seed_behaviors.py
if ($LASTEXITCODE -ne 0) { Write-Error "seed_behaviors.py failed"; exit 1 }

# Step 2: Detect behaviors
Write-Host ""
Write-Host "[2/4] Detecting behaviors in raw_bars (last $Days days)..." -ForegroundColor Yellow
if ($Tickers -ne "") {
    & $Python scripts\python\detector.py --tickers $Tickers.Split(" ") --days $Days
} else {
    & $Python scripts\python\detector.py --days $Days
}
if ($LASTEXITCODE -ne 0) { Write-Error "detector.py failed"; exit 1 }

# Step 3: Backtest behavior concepts
Write-Host ""
Write-Host "[3/4] Backtesting behavior concepts (min $MinSamples samples)..." -ForegroundColor Yellow
& $Python scripts\python\backtest_behavior_concepts.py --min-samples $MinSamples
if ($LASTEXITCODE -ne 0) { Write-Error "backtest_behavior_concepts.py failed"; exit 1 }

# Step 4: Analyze behavior interactions
Write-Host ""
Write-Host "[4/4] Analyzing behavior interactions (min $MinSamples co-occurrences)..." -ForegroundColor Yellow
& $Python scripts\python\analyze_behavior_interactions.py --min-samples $MinSamples
if ($LASTEXITCODE -ne 0) { Write-Error "analyze_behavior_interactions.py failed"; exit 1 }

Write-Host ""
Write-Host "=== Pipeline Complete ===" -ForegroundColor Green
