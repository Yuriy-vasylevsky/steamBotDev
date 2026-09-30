#!/usr/bin/env bash
# Safely deploy the current main branch on the DigitalOcean host.
set -Eeuo pipefail

project_dir="${STEAMSELL_DIR:-/opt/steambot}"
cd "$project_dir"

if [[ ! -f compose.yaml || ! -f .env ]]; then
  echo "compose.yaml or .env is missing in $project_dir" >&2
  exit 1
fi

git pull --ff-only
docker compose build app migrate
docker compose up -d

docker compose ps
docker compose logs --tail=50 app
