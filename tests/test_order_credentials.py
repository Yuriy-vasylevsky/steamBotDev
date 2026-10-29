import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from app.models import Order, Product
from app.ui import purchase_text
from app.worker import deliver_one


async def test_product_edits_do_not_change_paid_purchase(shop, payment):
    await shop.payment(payment, "credentials-snapshot")
    async with shop.sessions() as session, session.begin():
        product = await session.get(Product, 1)
        product.steam_login_encrypted = shop.vault.encrypt("replacement_login")
        product.steam_password_encrypted = shop.vault.encrypt("replacement_password")

    bot = AsyncMock()
    bot.send_message.return_value.message_id = 123
    assert await deliver_one(shop, bot)
    delivered = bot.send_message.call_args.args[1]
    assert "test_account" in delivered
    assert "password&lt;&amp;&gt;" in delivered
    assert "replacement_" not in delivered

    async with shop.sessions() as session:
        order = await session.get(Order, "a" * 32)
        product = await session.get(Product, 1)
        history = purchase_text(order, product, "ua", shop.vault)
        assert "test_account" in history
        assert "password&lt;&amp;&gt;" in history
        assert "replacement_" not in history


async def test_checkout_preserves_credentials_before_payment(shop):
    shop.mono.create.return_value = {"invoiceId": "new-invoice", "pageUrl": "https://example.test/pay"}
    order = await shop.checkout(2, 1)
    async with shop.sessions() as session, session.begin():
        product = await session.get(Product, 1)
        product.steam_login_encrypted = shop.vault.encrypt("new_login")
        product.steam_password_encrypted = shop.vault.encrypt("new_password")
    async with shop.sessions() as session:
        saved = await session.get(Order, order.id)
        assert shop.vault.decrypt(saved.steam_login_encrypted) == "test_account"
        assert shop.vault.decrypt(saved.steam_password_encrypted) == "password<&>"


def test_migration_preserves_existing_credentials():
    path = Path(__file__).parents[1] / "alembic/versions/0033_order_credentials.py"
    spec = importlib.util.spec_from_file_location("order_credentials", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with create_engine("sqlite://").begin() as connection:
        connection.execute(text(
            "CREATE TABLE products (id INTEGER PRIMARY KEY, "
            "steam_login_encrypted TEXT, steam_password_encrypted TEXT)"
        ))
        connection.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, product_id INTEGER)"))
        connection.execute(text("INSERT INTO products VALUES (1, 'encrypted-login', 'encrypted-password')"))
        connection.execute(text("INSERT INTO orders VALUES (1, 1)"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            connection.execute(text("UPDATE products SET steam_password_encrypted = 'replacement'"))
            row = connection.execute(text(
                "SELECT steam_login_encrypted, steam_password_encrypted FROM orders"
            )).one()
            assert tuple(row) == ("encrypted-login", "encrypted-password")
            migration.downgrade()
