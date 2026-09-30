# Перенесення SteamSell на DigitalOcean

Рекомендована конфігурація: Ubuntu 24.04, щонайменше 2 GB RAM, SSH-ключ і Cloud Firewall з вхідними TCP-портами 22 (лише ваша IP-адреса), 80 та 443. PostgreSQL, Redis і порт 8000 назовні не відкривайте.

## 1. DNS

Створіть `A`-запис, наприклад `bot.example.com`, який вказує на IPv4 Droplet. Дочекайтеся, поки команда `getent hosts bot.example.com` на сервері поверне правильну адресу.

## 2. Початкова інсталяція

```sh
ssh root@DROPLET_IP
git clone https://github.com/poegoranolo-maker/steamBot.git /opt/steambot
cd /opt/steambot
bash deploy/install-ubuntu.sh
nano .env
```

У `.env` замініть усі порожні та прикладні значення. `DOMAIN` має містити лише ім'я хоста, а `PUBLIC_BASE_URL` — ту саму адресу з `https://`:

```dotenv
DOMAIN=bot.example.com
PUBLIC_BASE_URL=https://bot.example.com
COMPOSE_PROFILES=production
```

Не генеруйте новий `ENCRYPTION_KEY`, якщо переносите чинну базу. Старий ключ потрібен для розшифрування Steam-даних, Gmail-токенів та інших секретів.

## 3. Перенесення чинної бази

На старому сервері спочатку зупиніть застосунок, щоб два процеси не отримували Telegram updates і база не змінювалася під час фінального дампа:

```sh
cd /path/to/old/steambot
docker compose stop app
docker compose exec -T db pg_dump -U steamsell -d steamsell -Fc > steamsell-transfer.dump
```

Скопіюйте `steamsell-transfer.dump` і старий `.env` захищеним каналом на новий сервер. Не передавайте ці файли через Git.

На новому сервері підніміть лише сховища та відновіть базу:

```sh
cd /opt/steambot
docker compose up -d db redis
docker compose cp steamsell-transfer.dump db:/tmp/steamsell-transfer.dump
docker compose exec db pg_restore -U steamsell -d steamsell --clean --if-exists --no-owner /tmp/steamsell-transfer.dump
```

Для нової порожньої інсталяції цей розділ пропустіть.

## 4. Запуск і перевірка

```sh
cd /opt/steambot
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 app caddy
curl https://bot.example.com/health
```

Caddy автоматично отримує і поновлює TLS-сертифікат. Додайте у Google OAuth точний redirect URI:

```text
https://bot.example.com/oauth/gmail/callback
```

Monobank використовує callback:

```text
https://bot.example.com/webhooks/monobank
```

Після перевірки виконайте тестові `/start`, `/admin`, Gmail OAuth і тестову оплату. Не запускайте старий `app` повторно з тим самим `BOT_TOKEN`.

## 5. Наступні оновлення

```sh
cd /opt/steambot
bash deploy/update.sh
```

Сервіс `backup` щодня створює dump у `/opt/steambot/backups` і зберігає його 14 днів. Налаштуйте також зашифровану offsite-копію: локальні dumps не захищають від втрати Droplet.
