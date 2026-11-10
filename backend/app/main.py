from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uuid
from time import monotonic

from app.ws.ws_consumer import trade_consumer, ws_consumer
from app.ws.connection_manager import ConnectionManager
from app.clients.redis_client import OrderBookRedisClient
from app.ws.coalesce import DeltaCoalescer
from app.ws.redis_subscriber import redis_orderbook_subscriber
from app.metrics import (
    record_snapshot_cache_hit,
    record_snapshot_cache_miss,
    record_snapshot_request,
    render_prometheus_metrics,
)

orderbook_manager = ConnectionManager()
trade_manager = ConnectionManager()
redis_client = OrderBookRedisClient()
orderbook_coalescer = DeltaCoalescer(flush_ms=100)

ALLOWED_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"}
SNAPSHOT_CACHE_TTL_SECONDS = 0.5
IDLE_TIMEOUT_SECONDS = 300
IDLE_CHECK_INTERVAL_SECONDS = 15

active_consumers: dict[str, asyncio.Task] = {}
last_activity: dict[str, float] = {}
consumer_locks: dict[str, asyncio.Lock] = {}
snapshot_cache: dict[str, tuple[float, dict]] = {}
snapshot_cache_locks: dict[str, asyncio.Lock] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.connect()
    subscriber_task = asyncio.create_task(
        redis_orderbook_subscriber(orderbook_manager, trade_manager, orderbook_coalescer)
    )
    coalescer_task = asyncio.create_task(orderbook_coalescer.flush_loop(orderbook_manager))
    idle_task = asyncio.create_task(idle_consumer_reaper())

    yield

    shutdown_tasks = [
        subscriber_task,
        coalescer_task,
        idle_task,
        *active_consumers.values(),
    ]

    for task in shutdown_tasks:
        task.cancel()

    await asyncio.gather(*shutdown_tasks, return_exceptions=True)
    await redis_client.close()

app = FastAPI(
    title="Order Book Backend",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://orderflow.sandertamm.eu",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _consumer_lock(symbol: str) -> asyncio.Lock:
    return consumer_locks.setdefault(symbol, asyncio.Lock())


def has_active_clients(symbol: str) -> bool:
    symbol = symbol.upper()
    return bool(orderbook_manager.clients.get(symbol)) or bool(
        trade_manager.clients.get(symbol)
    )


async def ensure_consumer_running(symbol: str):
    symbol = symbol.upper()
    last_activity[symbol] = monotonic()

    async with _consumer_lock(symbol):
        last_activity[symbol] = monotonic()
        started = False

        orderbook_key = f"{symbol}:orderbook"
        trade_key = f"{symbol}:trades"

        orderbook_task = active_consumers.get(orderbook_key)
        if orderbook_task is None or orderbook_task.done():
            active_consumers[orderbook_key] = asyncio.create_task(ws_consumer(symbol))
            print(f"Started Binance order book consumer for {symbol}")
            started = True

        trade_task = active_consumers.get(trade_key)
        if trade_task is None or trade_task.done():
            active_consumers[trade_key] = asyncio.create_task(trade_consumer(symbol))
            print(f"Started Binance trade consumer for {symbol}")
            started = True

        return started


async def stop_consumers(symbol: str):
    tasks = []

    for stream in ("orderbook", "trades"):
        task = active_consumers.pop(f"{symbol}:{stream}", None)

        if task is not None and not task.done():
            task.cancel()
            tasks.append(task)

    stopped = bool(tasks)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    snapshot_cache.pop(symbol, None)
    last_activity.pop(symbol, None)

    try:
        await redis_client.clear_orderbook(symbol)
        await redis_client.clear_trades(symbol)
    except Exception as e:
        print(f"{symbol}: failed to clear idle state: {e}")

    if stopped:
        print(f"Idle timeout: stopped Binance consumers for {symbol}")

    return stopped


async def idle_consumer_reaper():
    while True:
        await asyncio.sleep(IDLE_CHECK_INTERVAL_SECONDS)
        try:
            
            now = monotonic()

            for symbol in ALLOWED_SYMBOLS:
                if has_active_clients(symbol):
                    last_activity[symbol] = now
                    continue

                last_seen = last_activity.get(symbol)

                if last_seen is None or now - last_seen < IDLE_TIMEOUT_SECONDS:
                    continue

                async with _consumer_lock(symbol):
                    if has_active_clients(symbol):
                        last_activity[symbol] = monotonic()
                        continue

                    if monotonic() - last_activity.get(symbol, now) < IDLE_TIMEOUT_SECONDS:
                        continue

                    await stop_consumers(symbol)
        except Exception as e:
                    print(f"idle reaper error: {e}")

def get_cached_snapshot(symbol: str):
    entry = snapshot_cache.get(symbol)

    if not entry:
        return None

    expires_at, snapshot = entry

    if monotonic() >= expires_at:
        snapshot_cache.pop(symbol, None)
        return None

    record_snapshot_cache_hit(symbol)
    return snapshot

async def get_snapshot_with_cache(symbol: str):
    cached_snapshot = get_cached_snapshot(symbol)

    if cached_snapshot:
        return cached_snapshot

    lock = snapshot_cache_locks.setdefault(symbol, asyncio.Lock())

    async with lock:
        cached_snapshot = get_cached_snapshot(symbol)

        if cached_snapshot:
            return cached_snapshot

        snapshot = await redis_client.get_snapshot(symbol, 25)

        if not snapshot["bids"] and not snapshot["asks"]:
            snapshot["status"] = "warming_up"
        else:
            snapshot["status"] = "ready"

        snapshot_cache[symbol] = (
            monotonic() + SNAPSHOT_CACHE_TTL_SECONDS,
            snapshot,
        )
        record_snapshot_cache_miss(symbol)

        return snapshot

@app.get("/")
async def root():
    return {"message": "Order book backend is alive"}

@app.get("/metrics")
async def metrics():
    content, media_type = render_prometheus_metrics()
    return Response(content=content, media_type=media_type)

@app.get("/snapshot/{symbol}")
async def get_snapshot(symbol: str):
    symbol = symbol.upper()

    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=404, detail="Unsupported symbol")

    record_snapshot_request(symbol)
    await ensure_consumer_running(symbol)

    return await get_snapshot_with_cache(symbol)

@app.websocket("/ws/orderbook/{symbol}")
async def orderbook_websocket(websocket: WebSocket, symbol: str):
    if symbol.upper() not in ALLOWED_SYMBOLS:
        await websocket.close(code=1008)
        return
    
    await ensure_consumer_running(symbol)

    symbol = symbol.upper()
    
    client_id = str(uuid.uuid4())

    await orderbook_manager.connect(client_id, symbol, websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        orderbook_manager.disconnect(client_id, symbol)

@app.get("/trades/{symbol}")
async def get_recent_trades(symbol: str):
    if symbol.upper() not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=404, detail="Unsupported symbol")

    await ensure_consumer_running(symbol)
    return {
        "symbol": symbol.upper(),
        "trades": await redis_client.get_recent_trades(symbol.upper(), 50),
    }

@app.websocket("/ws/trades/{symbol}")
async def trades_websocket(websocket: WebSocket, symbol: str):
    if symbol.upper() not in ALLOWED_SYMBOLS:
        await websocket.close(code=1008)
        return

    await ensure_consumer_running(symbol)

    symbol = symbol.upper()
    client_id = str(uuid.uuid4())

    await trade_manager.connect(client_id, symbol, websocket)

    recent_trades = await redis_client.get_recent_trades(symbol, 50)
    await websocket.send_json({
        "type": "trade_snapshot",
        "symbol": symbol,
        "data": recent_trades,
    })

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        trade_manager.disconnect(client_id, symbol)

@app.get("/health")
async def health():
    return {"message": "App healthy"}

@app.get("/ready")
async def ready():
    try:
        pong = await redis_client.ping()
    except Exception:
        return {"message": "Redis down"}

    return {"message": pong}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
