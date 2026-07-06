import json
import redis.asyncio as aioredis

from app.metrics import record_orderbook_update, record_trade_update

REDIS_URL = "redis://:qwerty@localhost:6379"

async def redis_orderbook_subscriber(orderbook_manager, trade_manager, orderbook_coalescer):
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)

    pubsub = redis.pubsub()
    await pubsub.psubscribe("orderbook:*", "trades:*")

    print("Redis listener activated for order books and trades")

    async for message in pubsub.listen():
        if message["type"] != "pmessage":
            continue

        delta = json.loads(message["data"])

        channel = message["channel"]
        channel_type, symbol = channel.split(":", 1)

        if channel_type == "orderbook":
            record_orderbook_update(symbol, delta["side"])
            await orderbook_coalescer.add(symbol, delta)

        if channel_type == "trades":
            record_trade_update(symbol)
            await trade_manager.broadcast_to_symbol(symbol, {
                "type": "trade",
                "data": delta,
                "symbol": symbol,
            })
