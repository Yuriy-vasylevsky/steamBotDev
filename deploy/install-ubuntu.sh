#!/usr/bin/env bash
# Run from the repository root on a fresh Ubuntu 24.04 DigitalOcean Droplet:
# sudo bash deploy/install-ubuntu.sh
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run with: sudo bash deploy/install-ubuntu.sh"
  exit 1
fi

if [[ ! -f compose.yaml || ! -f .env.example ]]; then
  echo "Run this script from the SteamSell project directory."
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git docker.io docker-compose-v2 openssl python3
systemctl enable --now docker

if [[ ! -f .env ]]; then
  install -m 600 .env.example .env
  db_password="$(openssl rand -hex 24)"
  fernet_key="$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  sed -i \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${db_password}|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://steamsell:${db_password}@db:5432/steamsell|" \
    -e "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${fernet_key}|" .env
  echo ".env was created with a unique database password and encryption key."
fi

install -d -m 700 backups

echo
echo "Installation prerequisites are ready."
echo "1. Edit .env: nano .env"
echo "2. Set BOT_TOKEN, ADMIN_ID, MONO_TOKEN, SUPPORT_USERNAME and integration credentials."
echo "3. For HTTPS set DOMAIN and PUBLIC_BASE_URL=https://the-same-domain."
echo "4. Start production: docker compose up -d --build"
echo "   (.env.example enables the production profile through COMPOSE_PROFILES.)"
echo "5. Check: docker compose ps"
echo "          docker compose logs --tail=100 app caddy"
echo "          curl https://\${DOMAIN}/health"
