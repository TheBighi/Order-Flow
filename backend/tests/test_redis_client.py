import asyncio
import json

from app.clients.redis_client import OrderBookRedisClient


class FakeRedis:
    def __init__(self):
        self.calls = []

    async def zadd(self, key, mapping):
        self.calls.append(("zadd", key, mapping))

    async def hset(self, key, field=None, value=None, mapping=None):
        self.calls.append(("hset", key, field, value, mapping))

    async def zrem(self, key, member):
        self.calls.append(("zrem", key, member))

    async def hdel(self, key, field):
        self.calls.append(("hdel", key, field))

    async def publish(self, channel, payload):
        self.calls.append(("publish", channel, json.loads(payload)))

    async def zrangebyscore(self, key, minimum, maximum, start=0, num=None):
        self.calls.append(("zrangebyscore", key, minimum, maximum, start, num))
        return ["101.0", "102.0"]

    async def zrevrangebyscore(self, key, maximum, minimum, start=0, num=None):
        self.calls.append(("zrevrangebyscore", key, maximum, minimum, start, num))
        return ["100.0", "99.0"]

    async def hmget(self, key, *prices):
        self.calls.append(("hmget", key, prices))
        quantities = {
            "100.0": "1.5",
            "99.0": "2.0",
            "101.0": "0.75",
            "102.0": "1.25",
        }
        return [quantities[price] for price in prices]


def test_apply_delta_upserts_price_level_and_publishes_delta():
    async def run_test():
        fake_redis = FakeRedis()
        client = OrderBookRedisClient()
        client.redis = fake_redis
        row = {"side": "bid", "price": 100.0, "qty": 1.5, "timestamp": 1710000000000}

        await client.apply_delta("btcusdt", row)

        assert fake_redis.calls == [
            ("zadd", "orderbook:BTCUSDT:bids", {"100.0": 100.0}),
            ("hset", "orderbook:BTCUSDT:bid_qty", "100.0", 1.5, None),
            ("publish", "orderbook:BTCUSDT", row),
        ]

    asyncio.run(run_test())


def test_apply_delta_removes_empty_price_level_and_publishes_delete():
    async def run_test():
        fake_redis = FakeRedis()
        client = OrderBookRedisClient()
        client.redis = fake_redis
        row = {"side": "ask", "price": 101.0, "qty": 0.0, "timestamp": 1710000000001}

        await client.apply_delta("btcusdt", row)

        assert fake_redis.calls == [
            ("zrem", "orderbook:BTCUSDT:asks", "101.0"),
            ("hdel", "orderbook:BTCUSDT:ask_qty", "101.0"),
            ("publish", "orderbook:BTCUSDT", row),
        ]

    asyncio.run(run_test())


def test_get_snapshot_reads_best_bids_and_asks_with_quantities():
    async def run_test():
        fake_redis = FakeRedis()
        client = OrderBookRedisClient()
        client.redis = fake_redis

        snapshot = await client.get_snapshot("btcusdt", 2)

        assert snapshot == {
            "symbol": "BTCUSDT",
            "bids": [
                {"price": 100.0, "qty": 1.5},
                {"price": 99.0, "qty": 2.0},
            ],
            "asks": [
                {"price": 101.0, "qty": 0.75},
                {"price": 102.0, "qty": 1.25},
            ],
        }
        assert ("zrevrangebyscore", "orderbook:BTCUSDT:bids", "+inf", 0, 0, 2) in fake_redis.calls
        assert ("zrangebyscore", "orderbook:BTCUSDT:asks", 0, "+inf", 0, 2) in fake_redis.calls

    asyncio.run(run_test())
