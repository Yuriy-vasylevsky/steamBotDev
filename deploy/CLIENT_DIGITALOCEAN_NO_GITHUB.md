# Встановлення SteamSell на DigitalOcean без GitHub

Цей варіант передає код разом із робочим `.env` із папки на Windows-комп'ютері через `tar` і `scp`. Архів міститиме секрети — не завантажуйте його в Git, хмарні диски або публічні чати.

> Якщо Hetzner і DigitalOcean мають працювати одночасно, для DigitalOcean потрібен окремий Telegram-бот і новий `BOT_TOKEN`. Не запускайте два активні `app` з однаковим токеном.

## 1. Створити Droplet

У DigitalOcean створіть Droplet з Ubuntu 24.04 і щонайменше 2 GB RAM. У Cloud Firewall відкрийте:

- TCP `22` — бажано лише для вашої IP-адреси;
- TCP `80` і `443` — для всіх адрес;
- UDP `443` — необов'язково, для HTTP/3.

Запишіть IP нового сервера як `IP_DIGITALOCEAN`.

## 2. Запакувати код на Windows

Відкрийте PowerShell у корені локального проєкту:

```powershell
cd "C:\Users\yuriy\OneDrive\Документы\GitHub\steamBot"
```

Перед пакуванням відкрийте `.env` і переконайтеся, що для незалежного бота на DigitalOcean задано:

```dotenv
BOT_TOKEN=ТОКЕН_НОВОГО_БОТА
DOMAIN=bot2.example.com
PUBLIC_BASE_URL=https://bot2.example.com
COMPOSE_PROFILES=production
```

Якщо переносите копію чинної бази, залиште старий `ENCRYPTION_KEY`: без нього зашифровані дані не прочитаються. У `.env` не повинно бути команд `ssh`, `docker compose` або інших рядків поза форматом `НАЗВА=значення`.

Створіть архів із файлами, потрібними для запуску, та `.env`:

```powershell
tar -czf steamBot-deploy.tar.gz `
  app `
  alembic `
  deploy `
  scripts `
  .env `
  .env.example `
  alembic.ini `
  compose.yaml `
  Dockerfile `
  pyproject.toml `
  uv.lock
```

Архів не містить `.git`, `.venv`, кеші або backups, але містить робочі секрети з `.env`.

## 4. Передати файли на DigitalOcean

Із локального PowerShell:

```powershell
scp steamBot-deploy.tar.gz root@IP_DIGITALOCEAN:/tmp/
ssh root@IP_DIGITALOCEAN
```

## 5. Розпакувати та встановити

На DigitalOcean:

```sh
install -d -m 755 /opt/steamBot
tar -xzf /tmp/steamBot-deploy.tar.gz -C /opt/steamBot
chmod 600 /opt/steamBot/.env
cd /opt/steamBot
bash deploy/install-ubuntu.sh
docker compose config --quiet
```

Якщо остання команда нічого не вивела, конфігурація валідна.

## 6. Варіант А: запустити з порожньою базою

```sh
cd /opt/steamBot
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 migrate app caddy
```

Перевірте:

```sh
curl https://bot2.example.com/health
```

## 7. Варіант Б: скопіювати поточну базу з Hetzner

На Hetzner можна створити консистентний snapshot без зупинки старого незалежного бота:

```sh
cd /opt/steamBot
docker compose exec -T db pg_dump -U steamsell -d steamsell -Fc > steamsell-copy.dump
ls -lh steamsell-copy.dump
```

На локальному комп'ютері:

```powershell
scp root@IP_HETZNER:/opt/steamBot/steamsell-copy.dump .
scp steamsell-copy.dump root@IP_DIGITALOCEAN:/opt/steamBot/
```

На DigitalOcean:

```sh
cd /opt/steamBot
docker compose up -d db redis
docker compose cp steamsell-copy.dump db:/tmp/steamsell-copy.dump
docker compose exec db pg_restore -U steamsell -d steamsell --clean --if-exists --no-owner /tmp/steamsell-copy.dump
docker compose run --rm migrate
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 app caddy
```

Після копіювання бази сервери стають незалежними: нові товари, замовлення та налаштування між ними не синхронізуються.

## 8. Оновлювати код без GitHub

Після локальних змін повторно створіть архів і передайте його:

```powershell
cd "C:\Users\yuriy\OneDrive\Документы\GitHub\steamBot"
tar -czf steamBot-deploy.tar.gz `
  app `
  alembic `
  deploy `
  scripts `
  .env `
  .env.example `
  alembic.ini `
  compose.yaml `
  Dockerfile `
  pyproject.toml `
  uv.lock
scp steamBot-deploy.tar.gz root@IP_DIGITALOCEAN:/tmp/
```

На DigitalOcean:

```sh
tar -xzf /tmp/steamBot-deploy.tar.gz -C /opt/steamBot
cd /opt/steamBot
docker compose build app migrate
docker compose run --rm migrate
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail=50 migrate app caddy
```

Робочі `.env`, PostgreSQL volume, Redis volume та каталог `backups` при такому оновленні не перезаписуються.

## 9. Прибрати тимчасові файли

Після успішної перевірки на DigitalOcean:

```sh
rm -f /tmp/steamBot-deploy.tar.gz
```

На локальному комп'ютері після успішного встановлення видаліть архів, оскільки він містить `.env` із секретами:

```powershell
Remove-Item -LiteralPath .\steamBot-deploy.tar.gz
```
