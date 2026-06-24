# Stop InShow (Windows).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
docker compose down
Write-Host "InShow stopped."
