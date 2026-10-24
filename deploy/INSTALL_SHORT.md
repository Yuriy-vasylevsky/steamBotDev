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

## Перенесення бази даних зі старого бота

Найпростіший спосіб — завантажити резервну копію через адмін-панель старого
бота, передати файл на новий сервер через Termius і відновити його в
PostgreSQL.

> **Увага:** поточна база нового бота буде замінена даними з резервної копії.

### 1. Завантажте резервну копію

У старому боті завантажте файл із назвою приблизно такого вигляду:

```text
steamsell-backup-2026-09-30_12-00-00.dump
```

Для зручності перейменуйте його на:

```text
backup.dump
```

### 2. Передайте файл на новий сервер

У Termius підключіться до сервера `178.104.227.21` під користувачем `root`.
Через SFTP завантажте `backup.dump` у корінь папки бота:

```text
/root/steambot/backup.dump
```

### 3. Перевірте ключ шифрування

На новому сервері повинен використовуватися той самий `ENCRYPTION_KEY`, що й
у старого бота. Інакше перенесені Gmail-дані та інші зашифровані значення не
вдасться прочитати.

```bash
cd /root/steambot
nano .env
```

Після перевірки збережіть файл: **Ctrl+O**, **Enter**, потім **Ctrl+X**.

### 4. Відновіть базу і запустіть бота

Виконуйте команди **по одній**, переходячи до наступної лише тоді, коли
попередня завершилася без помилки:

```bash
cd /root/steambot

docker compose -p steamsell stop app backup
docker compose -p steamsell up -d db redis
docker compose -p steamsell cp backup.dump db:/tmp/backup.dump
docker compose -p steamsell exec -T db pg_restore --list /tmp/backup.dump
docker compose -p steamsell exec -T db dropdb -U steamsell --if-exists --force steamsell
docker compose -p steamsell exec -T db createdb -U steamsell -O steamsell steamsell
docker compose -p steamsell exec -T db pg_restore -U steamsell -d steamsell -O -x -e /tmp/backup.dump
bash deploy/start.sh
```

Команда `pg_restore --list` перевіряє, що файл є справною резервною копією.
Якщо вона повернула помилку, не виконуйте наступні команди: повторно завантажте
`backup.dump` на сервер.

### 5. Перевірте результат

```bash
docker compose -p steamsell ps
docker compose -p steamsell logs --tail=100 app
```

Контейнер `app` повинен мати статус `Up` і `healthy`.

### 6. Видаліть тимчасові копії

Після успішної перевірки:

```bash
rm -f /root/steambot/backup.dump
docker compose -p steamsell exec -T db rm -f /tmp/backup.dump
```

Якщо старий і новий сервери використовують однаковий `BOT_TOKEN`, не
запускайте старого бота після перенесення. Два екземпляри Telegram-бота з одним
токеном конфліктуватимуть між собою.
