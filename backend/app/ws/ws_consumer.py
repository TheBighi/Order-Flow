import asyncio
from ws_connector import stream_binance_depth

async def ws_consumer():
    while True: 
        try:
            async for depth_update in stream_binance_depth("ethusdt"):
                print(depth_update)
        except Exception as e:
            print(f"Connection lost: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(ws_consumer())
    except KeyboardInterrupt:
        print("Consumer stopped by user.")