from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uuid
from fastapi.middleware.cors import CORSMiddleware

from app.ws.ws_consumer import ws_consumer
from app.ws.connection_manager import ConnectionManager
from app.clients.redis_client import OrderBookRedisClient
from app.ws.redis_subscriber import redis_orderbook_subscriber
from app.metrics import render_prometheus_metrics

manager = ConnectionManager()
redis_client = OrderBookRedisClient()

ALLOWED_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"}

active_consumers: dict[str, asyncio.Task] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_client.connect()
    subscriber_task = asyncio.create_task(redis_orderbook_subscriber(manager))

    yield

    subscriber_task.cancel()

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

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def ensure_consumer_running(symbol: str):
    symbol = symbol.upper()

    if symbol in active_consumers:
        return

    active_consumers[symbol] = asyncio.create_task(ws_consumer(symbol))
    print(f"Started Binance consumer for {symbol}")
    return True

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
    if ensure_consumer_running(symbol):
        return "message: redis warming up"
    return await redis_client.get_snapshot(symbol.upper(), 25)

@app.websocket("/ws/orderbook/{symbol}")
async def orderbook_websocket(websocket: WebSocket, symbol: str):
    if symbol.upper() not in ALLOWED_SYMBOLS:
        await websocket.close(code=1008)
        return
    
    ensure_consumer_running(symbol)

    symbol = symbol.upper()
    
    client_id = str(uuid.uuid4())

    await manager.connect(client_id, symbol, websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(client_id, symbol)

@app.post("/test-broadcast")
async def test_broadcast(symbol: str = "BTCUSDT"):
    symbol = symbol.upper()

    await manager.broadcast_to_symbol(symbol, {
        "type": "test",
        "symbol": symbol,
        "message": "hello connected clients",
        "connected_clients": len(manager.clients.get(symbol, {})),
    })

    return {"sent_to": len(manager.clients.get(symbol, {}))}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
