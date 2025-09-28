param([switch]$Full=$false)
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = (Get-Location).Path
  Write-Host "== Running tests =="
  if ($Full) { pytest } else { pytest -q --maxfail=1 }
}
finally {
  Pop-Location
}