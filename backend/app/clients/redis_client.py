import json
import redis.asyncio as aioredis

REDIS_URL = "redis://:qwerty@localhost:6379"

# key schema
def _key(symbol: str, side: str) -> str:
    # e.g. "orderbook:BTCUSDT:bids" / "orderbook:BTCUSDT:asks"
    return f"orderbook:{symbol.upper()}:{side}s"

def _channel(symbol: str) -> str:
    return f"orderbook:{symbol.upper()}"


class OrderBookRedisClient:
    def __init__(self, url: str = REDIS_URL):
        self._url = url
        self.redis: aioredis.Redis | None = None

    async def connect(self):
        self.redis = await aioredis.from_url(self._url, decode_responses=True)

    async def close(self):
        if self.redis:
            await self.redis.aclose()

    # ------------------------------------------------------------------
    # core write — called once per normalised row
    # ------------------------------------------------------------------
    async def apply_delta(self, symbol: str, row: dict):
        """
        row: { side, price, qty, timestamp }
        - qty > 0  → ZADD  (upsert the level, score = price, member = price str)
        - qty == 0 → ZREM  (delete the level)
        Then PUBLISH the row as JSON to the symbol channel.
        """
        key = _key(symbol, row["side"])
        price = row["price"]
        qty   = row["qty"]

        if qty == 0.0:
            # remove the price level from the sorted set
            await self.redis.zrem(key, str(price))
        else:
            # score = price  → set stays sorted cheapest→most expensive
            # member = str(price) so each price level is unique
            await self.redis.zadd(key, {str(price): price})
            # store qty in a companion hash  orderbook:BTCUSDT:bid_qty
            qty_key = f"orderbook:{symbol.upper()}:{row['side']}_qty"
            await self.redis.hset(qty_key, str(price), qty)

        # publish every delta (including removals) so subscribers stay live
        await self.redis.publish(_channel(symbol), json.dumps(row))

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    async def get_best_asks(self, symbol: str, n: int = 25) -> list[dict]:
        """
        ZRANGEBYSCORE asks 0 +inf LIMIT 0 n
        Returns the n cheapest ask levels as [{ price, qty }].
        """
        key     = _key(symbol, "ask")
        qty_key = f"orderbook:{symbol.upper()}:ask_qty"

        prices = await self.redis.zrangebyscore(key, 0, "+inf", start=0, num=n)
        qtys   = await self.redis.hmget(qty_key, *prices) if prices else []

        return [
            {"price": float(p), "qty": float(q or 0)}
            for p, q in zip(prices, qtys)
        ]

    async def get_best_bids(self, symbol: str, n: int = 25) -> list[dict]:
        """
        Highest bids first — ZREVRANGEBYSCORE bids +inf 0 LIMIT 0 n
        """
        key     = _key(symbol, "bid")
        qty_key = f"orderbook:{symbol.upper()}:bid_qty"

        prices = await self.redis.zrevrangebyscore(key, "+inf", 0, start=0, num=n)
        qtys   = await self.redis.hmget(qty_key, *prices) if prices else []

        return [
            {"price": float(p), "qty": float(q or 0)}
            for p, q in zip(prices, qtys)
        ]