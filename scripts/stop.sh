#!/usr/bin/env bash
# Stop ShowSphere (Mac / Linux).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose down
echo "ShowSphere stopped."
