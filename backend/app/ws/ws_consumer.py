import sys
import json
import asyncio
import urllib.request
from app.ws.ws_connector import stream_binance_depth, stream_binance_trades
from app.ws.normalizer import normalize_delta, normalize_trade
from app.clients.redis_client import OrderBookRedisClient

BINANCE_REST_URL = "https://api.binance.com/api/v3/depth"
SNAPSHOT_LIMIT = 1000


def _fetch_snapshot_sync(symbol: str) -> dict:
    url = f"{BINANCE_REST_URL}?symbol={symbol.upper()}&limit={SNAPSHOT_LIMIT}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read())


async def fetch_snapshot(symbol: str) -> dict:
    return await asyncio.to_thread(_fetch_snapshot_sync, symbol)


async def ws_consumer(symbol: str = "btcusdt"):
    client = OrderBookRedisClient()
    await client.connect()

    try:
        while True:
            buffered = []
            last_applied_u = None
            synced = False
            snapshot_task = None

            try:
                stream = stream_binance_depth(symbol.lower())

                async for raw in stream:
                    if snapshot_task is None:
                        snapshot_task = asyncio.create_task(fetch_snapshot(symbol))

                    if not snapshot_task.done():
                        buffered.append(raw)
                        continue

                    if not synced:
                        snapshot = snapshot_task.result()
                        last_update_id = snapshot["lastUpdateId"]

                        await client.load_snapshot(
                            symbol.upper(), snapshot["bids"], snapshot["asks"]
                        )

                        pending = buffered + [raw]
                        buffered = []
                        applied_first = False

                        for event in pending:
                            if event["u"] <= last_update_id:
                                continue

                            if not applied_first:
                                if not (event["U"] <= last_update_id + 1 <= event["u"]):
                                    raise RuntimeError(
                                        f"{symbol}: snapshot did not align with "
                                        f"first live event, resyncing"
                                    )
                                applied_first = True
                            elif event["U"] != last_applied_u + 1:
                                raise RuntimeError(
                                    f"{symbol}: sequence gap detected "
                                    f"(expected U={last_applied_u + 1}, got {event['U']}), resyncing"
                                )

                            for row in normalize_delta(event):
                                await client.apply_delta(symbol.upper(), row)

                            last_applied_u = event["u"]

                        synced = True
                        continue

                    if raw["U"] != last_applied_u + 1:
                        raise RuntimeError(
                            f"{symbol}: sequence gap detected "
                            f"(expected U={last_applied_u + 1}, got {raw['U']}), resyncing"
                        )

                    for row in normalize_delta(raw):
                        await client.apply_delta(symbol.upper(), row)

                    last_applied_u = raw["u"]

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"{symbol}: {e}. Reconnecting and resyncing in 5 seconds...")
                await asyncio.sleep(5)
    finally:
        await client.close()


async def trade_consumer(symbol: str = "btcusdt"):
    client = OrderBookRedisClient()
    await client.connect()
    await client.clear_trades(symbol.upper())

    try:
        while True:
            try:
                async for raw_trade in stream_binance_trades(symbol.lower()):
                    trade = normalize_trade(raw_trade)
                    await client.apply_trade(symbol.upper(), trade)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"{symbol}: trade stream error {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
    finally:
        await client.close()


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "btcusdt"

    try:
        asyncio.run(ws_consumer(symbol))
    except KeyboardInterrupt:
        print("Consumer stopped by user.")
