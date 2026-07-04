import json
from time import perf_counter
import redis.asyncio as aioredis

from app.metrics import observe_redis_zrange

REDIS_URL = "redis://:qwerty@localhost:6379"

# key schema
def _key(symbol: str, side: str) -> str:
    # e.g. "orderbook:BTCUSDT:bids" / "orderbook:BTCUSDT:asks"
    return f"orderbook:{symbol.upper()}:{side}s"

def _channel(symbol: str) -> str:
    return f"orderbook:{symbol.upper()}"

def _trade_key(symbol: str) -> str:
    return f"trades:{symbol.upper()}:recent"

def _trade_channel(symbol: str) -> str:
    return f"trades:{symbol.upper()}"


class OrderBookRedisClient:
    def __init__(self, url: str = REDIS_URL):
        self._url = url
        self.redis: aioredis.Redis | None = None

    async def connect(self):
        self.redis = await aioredis.from_url(self._url, decode_responses=True)

    async def close(self):
        if self.redis:
            await self.redis.aclose()

    async def clear_orderbook(self, symbol: str):
        symbol = symbol.upper()

        await self.redis.delete(
            f"orderbook:{symbol}:bids",
            f"orderbook:{symbol}:asks",
            f"orderbook:{symbol}:bid_qty",
            f"orderbook:{symbol}:ask_qty",
        )

    async def clear_trades(self, symbol: str):
        await self.redis.delete(_trade_key(symbol))

    async def load_snapshot(self, symbol: str, bids: list[tuple[str, str]], asks: list[tuple[str, str]]):
        symbol = symbol.upper()
        await self.clear_orderbook(symbol)

        async def _load_side(side: str, levels: list[tuple[str, str]]):
            key = _key(symbol, side)
            qty_key = f"orderbook:{symbol}:{side}_qty"

            zadd_mapping = {}
            qty_mapping = {}

            for price_str, qty_str in levels:
                price = float(price_str)
                qty = float(qty_str)

                if qty == 0.0:
                    continue

                zadd_mapping[str(price)] = price
                qty_mapping[str(price)] = qty

            if zadd_mapping:
                await self.redis.zadd(key, zadd_mapping)
                await self.redis.hset(qty_key, mapping=qty_mapping)

        await _load_side("bid", bids)
        await _load_side("ask", asks)

    # ------------------------------------------------------------------
    # core write — called once per normalised
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
            # remove the price level from both the sorted set and the
            # companion qty hash — previously only zrem happened here,
            # leaving the qty hash growing forever
            qty_key = f"orderbook:{symbol.upper()}:{row['side']}_qty"
            await self.redis.zrem(key, str(price))
            await self.redis.hdel(qty_key, str(price))
        else:
            # score = price  → set stays sorted cheapest→most expensive
            # member = str(price) so each price level is unique
            await self.redis.zadd(key, {str(price): price})
            # store qty in a companion hash  orderbook:BTCUSDT:bid_qty
            qty_key = f"orderbook:{symbol.upper()}:{row['side']}_qty"
            await self.redis.hset(qty_key, str(price), qty)

        # publish every delta (including removals) so subscribers stay live
        await self.redis.publish(_channel(symbol), json.dumps(row))

    async def apply_trade(self, symbol: str, trade: dict):
        key = _trade_key(symbol)

        await self.redis.lpush(key, json.dumps(trade))
        await self.redis.ltrim(key, 0, 49)
        await self.redis.publish(_trade_channel(symbol), json.dumps(trade))

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

        start_time = perf_counter()
        prices = await self.redis.zrangebyscore(key, 0, "+inf", start=0, num=n)
        observe_redis_zrange(symbol, "ask", (perf_counter() - start_time) * 1000)

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

        start_time = perf_counter()
        prices = await self.redis.zrevrangebyscore(key, "+inf", 0, start=0, num=n)
        observe_redis_zrange(symbol, "bid", (perf_counter() - start_time) * 1000)

        qtys   = await self.redis.hmget(qty_key, *prices) if prices else []

        return [
            {"price": float(p), "qty": float(q or 0)}
            for p, q in zip(prices, qtys)
        ]
    
    async def get_snapshot(self, symbol: str, n: int = 25) -> dict:
        bids = await self.get_best_bids(symbol, n)
        asks = await self.get_best_asks(symbol, n)

        return {
            "symbol": symbol.upper(),
            "bids": bids,
            "asks": asks,
        }

    async def get_recent_trades(self, symbol: str, n: int = 50) -> list[dict]:
        trades = await self.redis.lrange(_trade_key(symbol), 0, n - 1)
        return [json.loads(trade) for trade in trades]
