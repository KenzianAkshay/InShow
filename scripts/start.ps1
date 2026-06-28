# Start ShowSphere (Windows). Builds and runs the compose stack.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
Write-Host "ShowSphere is starting at http://localhost:3000"
