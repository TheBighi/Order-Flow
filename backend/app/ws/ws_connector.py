import asyncio
import json
import logging
import websockets
from typing import AsyncGenerator

from app.metrics import record_binance_reconnect

logger = logging.getLogger(__name__)

async def stream_binance_depth(symbol: str = "btcusdt") -> AsyncGenerator[dict, None]:
    url = f"wss://stream.binance.com:9443/ws/{symbol}@depth"
    delay = 1  # Initial backoff delay in seconds
    max_delay = 60

    while True:
        try:
            logger.info(f"Connecting to {url}...")
            async with websockets.connect(url) as websocket:
                print("Connected! Listening for depth updates...")
                delay = 1  # Reset delay on successful connection
                
                async for message in websocket:
                    data = json.loads(message)
                    yield data
                    
        except (websockets.exceptions.ConnectionClosed, OSError) as e:
            logger.warning(f"Connection lost ({type(e).__name__}). Retrying in {delay}s...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Retrying in {delay}s...")

        record_binance_reconnect(symbol, "depth")
        await asyncio.sleep(delay)
        delay = min(delay * 2, max_delay)


async def stream_binance_trades(symbol: str = "btcusdt") -> AsyncGenerator[dict, None]:
    url = f"wss://stream.binance.com:9443/ws/{symbol}@trade"
    delay = 1
    max_delay = 60

    while True:
        try:
            logger.info(f"Connecting to {url}...")
            async with websockets.connect(url) as websocket:
                print(f"Connected! Listening for {symbol.upper()} trades...")
                delay = 1

                async for message in websocket:
                    data = json.loads(message)
                    yield data

        except (websockets.exceptions.ConnectionClosed, OSError) as e:
            logger.warning(f"Trade stream lost ({type(e).__name__}). Retrying in {delay}s...")
        except Exception as e:
            logger.error(f"Unexpected trade stream error: {e}. Retrying in {delay}s...")

        record_binance_reconnect(symbol, "trade")
        await asyncio.sleep(delay)
        delay = min(delay * 2, max_delay)
