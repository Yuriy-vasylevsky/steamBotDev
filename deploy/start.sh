#!/usr/bin/env bash

# Start or update SteamSell from the repository root:
# bash deploy/start.sh

set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -f .env ]]; then
  echo "Missing .env. Upload the production .env together with the bot." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Run: sudo bash deploy/install-ubuntu.sh" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is not installed. Run the server setup first." >&2
  exit 1
fi

# Keep container and network names stable regardless of the upload directory.
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-steamsell}"

docker compose config --quiet
docker compose up -d --build --remove-orphans
docker compose ps

health_command=(
  docker compose exec -T app /app/.venv/bin/python -c
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10)"
)

for attempt in {1..12}; do
  if "${health_command[@]}" >/dev/null 2>&1; then
    echo "SteamSell is running."
    exit 0
  fi
  sleep 5
done

echo "The app did not pass its health check. Recent logs:" >&2
docker compose logs --tail=100 app migrate >&2
exit 1
