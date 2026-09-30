# Встановлення SteamSell на сервер

Файли бота разом із готовим `.env` уже мають бути завантажені на сервер у
папку `/opt/steamSellDev`.

## 1. Підключіться до сервера

Відкрийте SSH-термінал у Termius і виконайте:

```bash
ssh root@77.42.71.244
cd /opt/steamSellDev
ls -la
```

У списку мають бути `compose.yaml`, `.env`, `Dockerfile` і папка `deploy`.

## 2. Встановіть Docker

Якщо Docker на сервері ще не встановлений, виконайте:

```bash
sudo bash deploy/install-ubuntu.sh
```

Якщо Docker уже встановлений, цей крок можна пропустити.

## 3. Перевірте `.env`

Файл `.env` уже завантажений разом із ботом, тому створювати або заповнювати
його заново не потрібно. Переконайтеся, що файл існує:

```bash
ls -la .env
chmod 600 .env
```

За потреби відкрити налаштування:

```bash
nano .env
```

Насамперед перевірте `BOT_TOKEN`, `ADMIN_ID`, `POSTGRES_PASSWORD`,
`DATABASE_URL`, `ENCRYPTION_KEY`, `MONO_TOKEN`, `SUPPORT_USERNAME` і
`MANUAL_CARD`.

У `DATABASE_URL` має бути той самий пароль, що й у `POSTGRES_PASSWORD`.
Зберегти файл у `nano`: **Ctrl+O**, **Enter**, потім **Ctrl+X**.

## 4. Запустіть бота

```bash
bash deploy/start.sh
```

Скрипт перевірить конфігурацію, збере контейнери, застосує міграції, запустить
бота та дочекається успішного healthcheck. Після перезавантаження сервера
контейнери запускатимуться автоматично.

## Перевірка

```bash
docker compose -p steamsell ps
docker compose -p steamsell logs --tail=100 app
curl -fsS https://77.42.71.244.sslip.io/health
```

У статусі контейнера `app` має бути `Up` і `healthy`, а остання команда має
повернути `{"status":"ok"}`.

Вихід із безперервного перегляду логів через `docker compose logs -f`:
**Ctrl+C**.

## Після повторного завантаження нових файлів

Не видаляйте серверний `.env` і Docker volumes. Для оновлення виконайте:

```bash
cd /opt/steamSellDev
chmod 600 .env
bash deploy/start.sh
```
