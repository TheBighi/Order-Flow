import asyncio

from app.ws.coalesce import DeltaCoalescer


class RecordingManager:
    def __init__(self):
        self.messages = []

    async def broadcast_to_symbol(self, symbol, message):
        self.messages.append((symbol, message))


def test_coalescer_keeps_latest_delta_per_symbol_side_and_price():
    async def run_test():
        coalescer = DeltaCoalescer(flush_ms=100)
        manager = RecordingManager()

        await coalescer.add("BTCUSDT", {"side": "bid", "price": 100.0, "qty": 1.0})
        await coalescer.add("BTCUSDT", {"side": "bid", "price": 100.0, "qty": 2.0})
        await coalescer.add("BTCUSDT", {"side": "ask", "price": 101.0, "qty": 3.0})

        async with coalescer.lock:
            batches = coalescer.pending
            coalescer.pending = {}

        for symbol, levels in batches.items():
            await manager.broadcast_to_symbol(
                symbol,
                {
                    "type": "delta_batch",
                    "data": list(levels.values()),
                    "symbol": symbol,
                },
            )

        assert manager.messages == [
            (
                "BTCUSDT",
                {
                    "type": "delta_batch",
                    "data": [
                        {"side": "bid", "price": 100.0, "qty": 2.0},
                        {"side": "ask", "price": 101.0, "qty": 3.0},
                    ],
                    "symbol": "BTCUSDT",
                },
            )
        ]
        assert coalescer.pending == {}

    asyncio.run(run_test())
