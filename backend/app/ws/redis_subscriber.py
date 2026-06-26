import json
import redis.asyncio as aioredis

REDIS_URL = "redis://:qwerty@localhost:6379"


async def redis_orderbook_subscriber(manager, symbol: str = "BTCUSDT"):
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)

    pubsub = redis.pubsub()
    await pubsub.subscribe(f"orderbook:{symbol}")

    print(f"Redis channel: orderbook:{symbol}")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue

        delta = json.loads(message["data"])

        print(delta)

        await manager.broadcast({
            "type": "delta",
            "data": delta,
        })