from datetime import timedelta
from unittest.mock import AsyncMock

from app.models import Order, PaymentReceipt, now
from app.worker import expire_receipt_reviews


async def test_manual_review_expires_after_24_hours_once(shop):
    async with shop.sessions() as session, session.begin():
        order = await session.get(Order, "a" * 32)
        order.payment_method = "receipt"
        receipt = PaymentReceipt(order_id=order.id, user_id=1,
            telegram_file_id="test", file_sha256="f" * 64,
            status="manual_review", manual_review_at=now() - timedelta(hours=23))
        session.add(receipt)
        await session.flush()
        receipt_id = receipt.id
    bot = AsyncMock()
    await expire_receipt_reviews(shop, bot)
    bot.send_message.assert_not_called()
    async with shop.sessions() as session, session.begin():
        receipt = await session.get(PaymentReceipt, receipt_id)
        assert receipt.status == "manual_review"
        receipt.manual_review_at = now() - timedelta(hours=25)
    await expire_receipt_reviews(shop, bot)
    async with shop.sessions() as session:
        assert (await session.get(PaymentReceipt, receipt_id)).status == "rejected"
        assert (await session.get(Order, "a" * 32)).status == "cancelled"
    await expire_receipt_reviews(shop, bot)
    assert bot.send_message.call_count == 1
