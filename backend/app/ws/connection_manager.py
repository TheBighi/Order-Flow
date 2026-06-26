from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.clients: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.clients[client_id] = websocket
        print(f"Client connected: {client_id}")

    def disconnect(self, client_id: str):
        self.clients.pop(client_id, None)
        print(f"Client disconnected: {client_id}")

    async def broadcast(self, message: dict):
        dead_clients = []

        for client_id, websocket in self.clients.items():
            try:
                await websocket.send_json(message)
            except Exception:
                dead_clients.append(client_id)

        for client_id in dead_clients:
            self.disconnect(client_id)