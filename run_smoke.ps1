# run_smoke.ps1 - Start API server if needed, run smoke_mvp.py, then clean up.

param(
  [string]$HostAddr = "127.0.0.1",
  [int]$Port = 8000,
  # App module for uvicorn: change if your entry point differs
  [string]$App = "fantasy_stocks.main:app",
  # Python executable to use
  [string]$Python = "python",
  # Smoke test script filename
  [string]$Smoke = "smoke_mvp.py"
)

# Build $base safely (avoid colon-within-interpolation issues)
$base = "http://" + $HostAddr + ":" + $Port

Write-Host "== Checking server at $base =="

# Check if something is already listening
$probe = $null
try {
  $probe = Test-NetConnection -ComputerName $HostAddr -Port $Port -WarningAction SilentlyContinue
} catch {
  $probe = $null
}

$serverStartedHere = $false
$proc = $null

if (-not ($probe -and $probe.TcpTestSucceeded)) {
  Write-Host "No server found. Starting uvicorn..."
  try {
    $args = @("-m","uvicorn", $App, "--host", $HostAddr, "--port", "$Port", "--reload")
    $proc = Start-Process -FilePath $Python -ArgumentList $args -PassThru -WindowStyle Hidden
    $serverStartedHere = $true
  } catch {
    Write-Host "Failed to start uvicorn with: $Python -m uvicorn $App --host $HostAddr --port $Port --reload"
    throw
  }

  # Wait for server to come up
  $maxTries = 30
  $ok = $false
  for ($i = 1; $i -le $maxTries; $i++) {
    try {
      $ping = Invoke-RestMethod "$base/health/ping" -Method Get -TimeoutSec 2
      if ($ping -and $ping.ok -eq $true) { $ok = $true; break }
    } catch {}
    Start-Sleep -Milliseconds 500
  }
  if (-not $ok) {
    Write-Host "Server did not become healthy in time."
    if ($proc) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    exit 1
  }
  Write-Host "Server is running. PID=$($proc.Id)"
} else {
  Write-Host "Server already running at $base"
}

Write-Host "== Running $Smoke =="
# Ensure we run the smoke script with this Python
& $Python $Smoke
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
  Write-Host "$Smoke failed. exit=$exitCode"
} else {
  Write-Host "$Smoke passed."
}

# Stop uvicorn if we started it
if ($serverStartedHere -and $proc) {
  Write-Host "Stopping the uvicorn process we started (PID=$($proc.Id))..."
  try {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
  } catch {}
}

exit $exitCode
