from unittest.mock import AsyncMock

from sqlalchemy import select

from app.models import Broadcast, User
from app.worker import broadcast_batch


async def test_broadcast_is_sent_only_to_subscribed_users(shop):
    async with shop.sessions() as session, session.begin():
        assert (await session.get(User, 1)).broadcast_subscribed is True
        (await session.get(User, 2)).broadcast_subscribed = False
        session.add(
            Broadcast(payload={"text": "News", "photo": None, "entities": []})
        )
    bot = AsyncMock()
    await broadcast_batch(shop, bot)
    await broadcast_batch(shop, bot)
    recipient_ids = [call.args[0] for call in bot.send_message.await_args_list]
    assert 1 in recipient_ids
    assert 2 not in recipient_ids
    async with shop.sessions() as session:
        assert (await session.scalar(select(Broadcast))).status == "completed"
