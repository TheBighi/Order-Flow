import asyncio


class DeltaCoalescer:
    def __init__(self, flush_ms: int = 100):
        self.flush_seconds = flush_ms / 1000
        self.pending: dict[str, dict[str, dict]] = {}
        self.lock = asyncio.Lock()

    async def add(self, symbol: str, delta: dict):
        side = delta["side"]
        price = str(delta["price"])
        level_key = f"{side}:{price}"

        async with self.lock:
            if symbol not in self.pending:
                self.pending[symbol] = {}

            self.pending[symbol][level_key] = delta

    async def flush_loop(self, manager):
        while True:
            await asyncio.sleep(self.flush_seconds)

            async with self.lock:
                batches = self.pending
                self.pending = {}

            for symbol, levels in batches.items():
                if not levels:
                    continue

                await manager.broadcast_to_symbol(symbol, {
                    "type": "delta_batch",
                    "data": list(levels.values()),
                    "symbol": symbol,
                })
