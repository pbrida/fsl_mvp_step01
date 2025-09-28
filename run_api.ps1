param([int]$Port = 8000, [switch]$NoReload)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Get-Location).Path

$cmd = "uvicorn fantasy_stocks.main:app --host 127.0.0.1 --port $Port"
if (-not $NoReload) { $cmd += " --reload" }

Write-Host "Starting: $cmd"
Invoke-Expression $cmd