from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.ws.connection_manager import ConnectionManager
from app.clients.redis_client import OrderBookRedisClient
from app.ws.redis_subscriber import redis_orderbook_subscriber
from contextlib import asynccontextmanager
import asyncio

import uuid

@asynccontextmanager
async def lifespan(app: FastAPI):
    subscriber_task = asyncio.create_task(redis_orderbook_subscriber(manager))

    yield

    subscriber_task.cancel()

app = FastAPI(
    title="Order Book Backend",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

manager = ConnectionManager()
redis_client = OrderBookRedisClient()

@app.get("/")
async def root():
    return {"message": "Order book backend is alive"}

@app.websocket("/ws/orderbook/{symbol}")
async def orderbook_websocket(websocket: WebSocket, symbol: str):
    symbol = symbol.upper()
    client_id = str(uuid.uuid4())

    await manager.connect(client_id, symbol, websocket)

    await redis_client.connect()
    snapshot = await redis_client.get_snapshot(symbol, 25)

    await websocket.send_json({
        "type": "snapshot",
        "data": snapshot,
    })

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(client_id, symbol)

@app.post("/test-broadcast")
async def test_broadcast():
    await manager.broadcast({
        "type": "test",
        "message": "hello connected clients",
        "connected_clients": len(manager.clients),
    })

    return {"sent_to": len(manager.clients)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
