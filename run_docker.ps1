param([switch]$Rebuild=$false)
$ErrorActionPreference = "Stop"
if ($Rebuild -or -not (docker images -q fsl_mvp:dev)) { docker build -t fsl_mvp:dev . }
docker rm -f fsl_mvp_dev 2>$null
docker run -d --name fsl_mvp_dev -p 8000:8000 fsl_mvp:dev | Out-Null
Write-Host "Waiting for health..."
Start-Sleep -Seconds 2
try {
  $resp = Invoke-RestMethod http://127.0.0.1:8000/health/ping
  $resp | ConvertTo-Json
} catch {
  Write-Warning "Health check failed. Container logs:"
  docker logs fsl_mvp_dev
  throw
}