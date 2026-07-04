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
    """
    Blocking REST call — run via asyncio.to_thread so it doesn't stall
    the event loop. No extra HTTP dependency required.
    """
    url = f"{BINANCE_REST_URL}?symbol={symbol.upper()}&limit={SNAPSHOT_LIMIT}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read())


async def fetch_snapshot(symbol: str) -> dict:
    return await asyncio.to_thread(_fetch_snapshot_sync, symbol)


async def ws_consumer(symbol: str = "btcusdt"):
    client = OrderBookRedisClient()
    await client.connect()

    while True:
        # Per Binance's documented procedure for maintaining a local order
        # book: 1) open the diff stream and buffer events, 2) fetch a REST
        # snapshot with lastUpdateId, 3) discard buffered events where
        # u <= lastUpdateId, 4) the first applied event must satisfy
        # U <= lastUpdateId+1 <= u, 5) each subsequent event's U must equal
        # the previous event's u+1 — any gap means resync from step 1.
        buffered = []
        last_applied_u = None
        synced = False
        snapshot_task = None

        try:
            stream = stream_binance_depth(symbol.lower())

            async for raw in stream:
                # Don't request the snapshot until buffering has actually
                # started (i.e. the websocket is live and yielding events).
                # Firing the REST call at the same instant we start
                # connecting the websocket races the handshake — on a
                # busy book the snapshot can end up newer than expected
                # relative to the first buffered event, or there's a gap
                # nothing buffered, and the U/lastUpdateId alignment check
                # below fails every single time instead of occasionally.
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
                            continue  # older than snapshot, discard

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

        except Exception as e:
            print(f"{symbol}: {e}. Reconnecting and resyncing in 5 seconds...")
            await asyncio.sleep(5)


async def trade_consumer(symbol: str = "btcusdt"):
    client = OrderBookRedisClient()
    await client.connect()
    await client.clear_trades(symbol.upper())

    while True:
        try:
            async for raw_trade in stream_binance_trades(symbol.lower()):
                trade = normalize_trade(raw_trade)
                await client.apply_trade(symbol.upper(), trade)

        except Exception as e:
            print(f"{symbol}: trade stream error {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "btcusdt"

    try:
        asyncio.run(ws_consumer(symbol))
    except KeyboardInterrupt:
        print("Consumer stopped by user.")
