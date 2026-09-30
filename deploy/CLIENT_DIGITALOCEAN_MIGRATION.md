# Перенесення SteamSell з Hetzner на DigitalOcean

## 1. Створити сервер

У DigitalOcean створіть Droplet:

- Ubuntu 24.04;
- щонайменше 2 GB RAM;
- SSH-ключ для входу;
- відкриті порти `22`, `80` і `443`.

Направте домен бота на IP нового Droplet і підключіться:

```sh
ssh root@IP_DIGITALOCEAN
```

## 2. Встановити проєкт на DigitalOcean

```sh
git clone https://github.com/poegoranolo-maker/steamBot.git /opt/steamBot
cd /opt/steamBot
bash deploy/install-ubuntu.sh
```

GitHub URL потрібно вставляти без квадратних і круглих дужок.

## 3. Перенести `.env`

На локальному комп'ютері:

```powershell
scp root@IP_HETZNER:/opt/steamBot/.env .
scp .env root@IP_DIGITALOCEAN:/opt/steamBot/.env
```

На DigitalOcean:

```sh
cd /opt/steamBot
chmod 600 .env
nano .env
```

Додайте або перевірте:

```dotenv
DOMAIN=bot.example.com
PUBLIC_BASE_URL=https://bot.example.com
COMPOSE_PROFILES=production
```

Замініть `bot.example.com` справжнім доменом. Не змінюйте старі `ENCRYPTION_KEY`, `BOT_TOKEN`, `MONO_TOKEN` та інші секрети.

Перевірте файл:

```sh
docker compose config --quiet
```

Відсутність повідомлень означає, що конфігурація валідна.

## 4. Зупинити бот і створити backup на Hetzner

На Hetzner:

```sh
cd /opt/steamBot
docker compose stop app
docker compose exec -T db pg_dump -U steamsell -d steamsell -Fc > steamsell-transfer.dump
ls -lh steamsell-transfer.dump
```

Не запускайте старий `app` після створення фінального backup.

## 5. Передати backup на DigitalOcean

На Hetzner:

```sh
scp /opt/steamBot/steamsell-transfer.dump root@IP_DIGITALOCEAN:/opt/steamBot/
```

## 6. Відновити базу на DigitalOcean

```sh
cd /opt/steamBot
docker compose up -d db redis
docker compose cp steamsell-transfer.dump db:/tmp/steamsell-transfer.dump
docker compose exec db pg_restore -U steamsell -d steamsell --clean --if-exists --no-owner /tmp/steamsell-transfer.dump
```

## 7. Запустити бот

```sh
cd /opt/steamBot
git remote set-url origin https://github.com/poegoranolo-maker/steamBot.git
git pull --ff-only origin main
docker compose build
docker compose run --rm migrate
docker compose up -d --force-recreate
```

Перевірте запуск:

```sh
docker compose ps
docker compose logs --tail=50 migrate app caddy
curl https://bot.example.com/health
```

## 8. Фінальна перевірка

У Telegram перевірте:

- `/start`;
- `/admin`;
- товари та попередні замовлення;
- Gmail OAuth;
- тестову оплату;
- автоматичну видачу товару.

Одночасно має працювати лише один контейнер `app` із цим `BOT_TOKEN`.

## Подальші оновлення

```sh
cd /opt/steamBot
bash deploy/update.sh
```

## Відкат на Hetzner

Якщо новий сервер не працює:

1. Зупиніть застосунок на DigitalOcean:

   ```sh
   cd /opt/steamBot
   docker compose stop app
   ```

2. Поверніть DNS-запис на IP Hetzner.
3. Запустіть старий застосунок на Hetzner:

   ```sh
   cd /opt/steamBot
   docker compose up -d app
   ```
