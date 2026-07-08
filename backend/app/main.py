from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uuid

from app.ws.ws_consumer import trade_consumer, ws_consumer
from app.ws.connection_manager import ConnectionManager
from app.clients.redis_client import OrderBookRedisClient
from app.ws.coalesce import DeltaCoalescer
from app.ws.redis_subscriber import redis_orderbook_subscriber
from app.metrics import record_snapshot_request, render_prometheus_metrics

orderbook_manager = ConnectionManager()
trade_manager = ConnectionManager()
redis_client = OrderBookRedisClient()
orderbook_coalescer = DeltaCoalescer(flush_ms=100)

ALLOWED_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"}

active_consumers: dict[str, asyncio.Task] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.connect()
    subscriber_task = asyncio.create_task(
        redis_orderbook_subscriber(orderbook_manager, trade_manager, orderbook_coalescer)
    )
    coalescer_task = asyncio.create_task(orderbook_coalescer.flush_loop(orderbook_manager))

    yield

    shutdown_tasks = [subscriber_task, coalescer_task, *active_consumers.values()]

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
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def ensure_consumer_running(symbol: str):
    symbol = symbol.upper()

    started = False

    orderbook_key = f"{symbol}:orderbook"
    trade_key = f"{symbol}:trades"

    if orderbook_key not in active_consumers:
        active_consumers[orderbook_key] = asyncio.create_task(ws_consumer(symbol))
        print(f"Started Binance order book consumer for {symbol}")
        started = True

    if trade_key not in active_consumers:
        active_consumers[trade_key] = asyncio.create_task(trade_consumer(symbol))
        print(f"Started Binance trade consumer for {symbol}")
        started = True

    return started

@app.get("/")
async def root():
    return {"message": "Order book backend is alive"}

@app.get("/metrics")
async def metrics():
    content, media_type = render_prometheus_metrics()
    return Response(content=content, media_type=media_type)

@app.get("/snapshot/{symbol}")
async def get_snapshot(symbol: str):
    if symbol.upper() not in ALLOWED_SYMBOLS:
        return

    record_snapshot_request(symbol)
    ensure_consumer_running(symbol)
    snapshot = await redis_client.get_snapshot(symbol.upper(), 25)

    if not snapshot["bids"] and not snapshot["asks"]:
        snapshot["status"] = "warming_up"
    else:
        snapshot["status"] = "ready"

    return snapshot

@app.websocket("/ws/orderbook/{symbol}")
async def orderbook_websocket(websocket: WebSocket, symbol: str):
    if symbol.upper() not in ALLOWED_SYMBOLS:
        await websocket.close(code=1008)
        return
    
    ensure_consumer_running(symbol)

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
        return

    ensure_consumer_running(symbol)
    return {
        "symbol": symbol.upper(),
        "trades": await redis_client.get_recent_trades(symbol.upper(), 50),
    }

@app.websocket("/ws/trades/{symbol}")
async def trades_websocket(websocket: WebSocket, symbol: str):
    if symbol.upper() not in ALLOWED_SYMBOLS:
        await websocket.close(code=1008)
        return

    ensure_consumer_running(symbol)

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

@app.post("/test-broadcast")
async def test_broadcast(symbol: str = "BTCUSDT"):
    symbol = symbol.upper()

    await orderbook_manager.broadcast_to_symbol(symbol, {
        "type": "test",
        "symbol": symbol,
        "message": "hello connected clients",
        "connected_clients": len(orderbook_manager.clients.get(symbol, {})),
    })

    return {"sent_to": len(orderbook_manager.clients.get(symbol, {}))}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
