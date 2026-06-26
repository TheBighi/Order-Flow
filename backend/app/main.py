from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.ws.connection_manager import ConnectionManager

import uuid

app = FastAPI(
    title="Order Book Backend",
    openapi_url="/openapi.json",
)

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"message": "Order book backend is alive"}

@app.websocket("/ws/orderbook")
async def orderbook_websocket(websocket: WebSocket):
    client_id = str(uuid.uuid4())

    await manager.connect(client_id, websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(client_id)

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
