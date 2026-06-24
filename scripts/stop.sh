#!/usr/bin/env bash
# Stop InShow (Mac / Linux).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose down
echo "InShow stopped."
