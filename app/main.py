import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager, suppress

import httpx
from aiogram import Bot
from aiogram.fsm.storage.redis import RedisEventIsolation, RedisStorage
from aiogram.types import BotCommand
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.access import is_admin
from app.bot import create_dispatcher
from app.config import config
from app.db import database
from app.gmail import Gmail
from app.models import User
from app.monobank import Monobank
from app.security import Vault
from app.services import Shop, setting
from app.worker import worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    cfg = config()
    engine, sessions = database(cfg.database_url)
    redis = Redis.from_url(cfg.redis_url, decode_responses=True)
    await redis.ping()
    vault = Vault(cfg.encryption_key.get_secret_value())
    client = httpx.AsyncClient(timeout=httpx.Timeout(20), follow_redirects=False)
    mono = Monobank(cfg.mono_token.get_secret_value(), client)
    async with sessions() as session:
        await session.execute(text("SELECT 1"))
        saved = await setting(session, "mono_token")
        if saved:
            mono.token = vault.decrypt(saved)
    shop = Shop(cfg, sessions, vault, mono, Gmail(cfg, client), redis)
    bot = Bot(cfg.bot_token.get_secret_value())
    await bot.set_my_commands(
        [
            BotCommand(command="menu", description="Відкрити головне меню"),
            BotCommand(command="start", description="Перезапустити бота"),
        ]
    )
    storage = RedisStorage(redis, state_ttl=1800, data_ttl=1800)
    dp = create_dispatcher(shop, storage)
    dp.fsm.events_isolation = RedisEventIsolation(redis, lock_kwargs={"timeout": 120})
    app.state.shop, app.state.engine = shop, engine
    tasks = [
        asyncio.create_task(dp.start_polling(bot, handle_signals=False, close_bot_session=False)),
        asyncio.create_task(worker(shop, bot)),
    ]
    app.state.tasks = tasks
    log.info("shop_started")
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        await bot.session.close()
        await client.aclose()
        await redis.aclose()
        await engine.dispose()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


PUBLIC_HEADERS = {
    "Cache-Control": "public, max-age=300",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def public_page(title: str, body: str) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} — SteamSell</title>
  <style>
    :root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; }}
    body {{ margin: 0; background: #0b1220; color: #e5e7eb; line-height: 1.65; }}
    main {{ max-width: 760px; margin: 0 auto; padding: 56px 24px 72px; }}
    h1, h2 {{ color: #fff; line-height: 1.2; }} h1 {{ font-size: 2.25rem; }}
    h2 {{ margin-top: 2rem; }} a {{ color: #60a5fa; }}
    .card {{ background: #111b2e; border: 1px solid #26344d; border-radius: 18px; padding: 28px; }}
    nav {{ margin-top: 32px; display: flex; gap: 18px; flex-wrap: wrap; }}
    small {{ color: #9ca3af; }}
  </style>
</head>
<body><main><div class="card">{body}
<nav><a href="/">Головна</a><a href="/privacy">Політика конфіденційності</a><a href="/terms">Умови використання</a></nav>
</div></main></body></html>"""
    return HTMLResponse(html, headers=PUBLIC_HEADERS)


@app.get("/", response_class=HTMLResponse)
async def home():
    return public_page(
        "Головна",
        """<h1>SteamSell</h1>
<p>SteamSell — Telegram-магазин цифрових товарів. Після підтвердженої покупки бот надає покупцеві дані придбаного товару та, за запитом, допомагає отримати пов’язаний код Steam Guard.</p>
<h2>Як використовується Gmail</h2>
<p>Власник магазину добровільно підключає службову Gmail-скриньку через Google OAuth. Застосунок використовує доступ лише для читання, щоб знайти актуальний лист із кодом Steam Guard для придбаного облікового запису. SteamSell не надсилає, не змінює і не видаляє листи.</p>
<p>Підключення Gmail доступне тільки адміністраторам магазину. Покупцям не потрібно підключати власний Google-акаунт.</p>""",
    )


@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return public_page(
        "Політика конфіденційності",
        """<h1>Політика конфіденційності</h1><small>Оновлено: 28 вересня 2026 року</small>
<p>Ця політика описує обробку даних сервісом SteamSell — Telegram-магазином цифрових товарів.</p>
<h2>Які дані ми обробляємо</h2>
<p>Сервіс обробляє Telegram ID, ім’я та мову користувача, відомості про замовлення й оплату. Під час підключення службової Gmail-скриньки ми отримуємо адресу скриньки, OAuth refresh token і доступ лише для читання листів через scope <code>gmail.readonly</code>.</p>
<h2>Навіщо потрібні дані Gmail</h2>
<p>Доступ використовується тільки для пошуку свіжих листів із кодами Steam Guard та передачі відповідного коду покупцеві, який придбав пов’язаний цифровий товар. Сервіс не надсилає, не редагує та не видаляє листи.</p>
<h2>Зберігання і захист</h2>
<p>OAuth refresh tokens та облікові дані товарів зберігаються у зашифрованому вигляді. Коди й токени не записуються до журналів застосунку. Доступ мають лише уповноважені адміністратори та автоматизовані компоненти, необхідні для роботи сервісу.</p>
<h2>Передача третім особам</h2>
<p>Ми не продаємо персональні дані. Дані передаються лише постачальникам, необхідним для роботи сервісу: Google для Gmail API, Telegram для роботи бота, платіжному провайдеру для обробки платежів та інфраструктурному хостингу. Розкриття також можливе, якщо цього вимагає закон.</p>
<p>Використання інформації, отриманої через Google API, відповідає <a href="https://developers.google.com/terms/api-services-user-data-policy">Google API Services User Data Policy</a>, включно з вимогами Limited Use.</p>
<h2>Строк зберігання та видалення</h2>
<p>Дані зберігаються лише стільки, скільки потрібно для роботи сервісу, обліку замовлень і виконання юридичних обов’язків. Адміністратор може від’єднати Gmail-скриньку у боті та відкликати доступ у налаштуваннях Google-акаунта. Щоб подати запит на доступ, виправлення або видалення даних, зверніться до <a href="https://t.me/Kotkrotua">@Kotkrotua у Telegram</a>.</p>""",
    )


@app.get("/terms", response_class=HTMLResponse)
async def terms():
    return public_page(
        "Умови використання",
        """<h1>Умови використання</h1><small>Оновлено: 28 вересня 2026 року</small>
<p>Використовуючи SteamSell, ви погоджуєтесь із цими умовами та політикою конфіденційності.</p>
<h2>Призначення сервісу</h2>
<p>SteamSell забезпечує продаж і автоматизовану видачу цифрових товарів у Telegram. Користувач зобов’язується надавати коректні дані та не використовувати сервіс для шахрайства, несанкціонованого доступу чи іншої незаконної діяльності.</p>
<h2>Google та Gmail</h2>
<p>Підключати Gmail можуть лише особи, які мають право надати доступ до відповідної скриньки. Доступ можна відкликати будь-коли в налаштуваннях Google-акаунта.</p>
<h2>Підтримка</h2>
<p>З питань щодо замовлень, доступу до даних або цих умов звертайтеся до <a href="https://t.me/Kotkrotua">@Kotkrotua у Telegram</a>.</p>""",
    )


@app.get("/health")
async def health(request: Request):
    try:
        await request.app.state.shop.redis.ping()
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        if any(task.done() for task in request.app.state.tasks):
            raise RuntimeError()
        return {"status": "ok"}
    except Exception:
        return JSONResponse({"status": "unhealthy"}, status_code=503)


@app.post("/webhooks/monobank")
async def monobank_webhook(request: Request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            return JSONResponse({"error": "too_large"}, status_code=413)
    shop = request.app.state.shop
    try:
        if not await shop.mono.verify(bytes(body), request.headers.get("X-Sign", "")):
            return JSONResponse({"error": "invalid_signature"}, status_code=401)
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError()
        await shop.payment(payload, hashlib.sha256(body).hexdigest())
        return {"status": "ok"}
    except (ValueError, TypeError):
        return JSONResponse({"error": "invalid_payload"}, status_code=400)
    except LookupError:
        return JSONResponse({"error": "retry_later"}, status_code=503)
    except Exception:
        log.warning("payment_webhook_failed")
        return JSONResponse({"error": "temporary_failure"}, status_code=503)


@app.get("/oauth/gmail/callback", response_class=HTMLResponse)
async def gmail_callback(request: Request, state: str = "", code: str = "", error: str = ""):
    shop = request.app.state.shop
    headers = {
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    }
    if len(state) > 100 or not state:
        return HTMLResponse("Invalid state", status_code=400, headers=headers)
    admin_id = await shop.redis.getdel("oauth:" + state)
    admin = None
    if admin_id:
        async with shop.sessions() as session:
            admin = await session.get(User, int(admin_id))
    if not admin_id or not is_admin(shop.cfg, int(admin_id), admin):
        return HTMLResponse(
            "Authorization expired. Start again in Telegram.", status_code=400, headers=headers
        )
    if error or not code:
        return HTMLResponse("Authorization cancelled. Return to Telegram.", status_code=400, headers=headers)
    try:
        credentials = await shop.gmail.exchange(code)
        await shop.redis.set("gmail:draft:" + state, shop.vault.pack(credentials), ex=1800)
    except Exception:
        log.warning("gmail_oauth_failed")
        return HTMLResponse("Connection failed. Start again in Telegram.", status_code=400, headers=headers)
    return HTMLResponse("Gmail connected. Return to Telegram and confirm the connection.", headers=headers)
