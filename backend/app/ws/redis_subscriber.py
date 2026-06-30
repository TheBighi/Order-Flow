import json
import redis.asyncio as aioredis

REDIS_URL = "redis://:qwerty@localhost:6379"


async def redis_orderbook_subscriber(manager):
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)

    pubsub = redis.pubsub()
    await pubsub.psubscribe("orderbook:*")

    print("Redis listener activated")

    async for message in pubsub.listen():
        if message["type"] != "pmessage":
            continue

        delta = json.loads(message["data"])

        channel = message["channel"]
        symbol = channel.split(":")[1]  
    
        await manager.broadcast_to_symbol(symbol, {
            "type": "delta",
            "data": delta,
            "symbol": symbol,
        })
