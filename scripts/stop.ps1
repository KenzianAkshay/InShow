# Stop ShowSphere (Windows).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose down
Write-Host "ShowSphere stopped."
