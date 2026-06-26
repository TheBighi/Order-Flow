import asyncio
from app.ws.ws_connector import stream_binance_depth
from app.ws.normalizer import normalize_delta
from app.clients.redis_client import OrderBookRedisClient

client = OrderBookRedisClient()

async def ws_consumer(symbol: str = "btcusdt"):
    await client.connect()
    await client.clear_orderbook("BTCUSDT")
    while True:
        try:
            async for depth_update in stream_binance_depth(symbol):
                rows = normalize_delta(depth_update)
                for row in rows:
                    await client.apply_delta(symbol.upper(), row)
        except Exception as e:
            print(f"Connection lost: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(ws_consumer())
    except KeyboardInterrupt:
        print("Consumer stopped by user.")