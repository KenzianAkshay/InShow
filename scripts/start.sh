#!/usr/bin/env bash
# Start InShow (Mac / Linux). Builds and runs the compose stack.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
docker compose up -d --build
echo "InShow is starting at http://localhost:3000"
