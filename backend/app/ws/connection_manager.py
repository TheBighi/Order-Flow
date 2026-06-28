from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.clients: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, client_id: str, symbol: str, websocket: WebSocket):
        await websocket.accept()

        symbol = symbol.upper()

        if symbol not in self.clients:
            self.clients[symbol] = {}

        self.clients[symbol][client_id] = websocket

        print(f"Client connected: {client_id} watching {symbol}")

    def disconnect(self, client_id: str, symbol: str):
        symbol = symbol.upper()
        symbol_clients = self.clients.get(symbol)

        if not symbol_clients:
            return

        symbol_clients.pop(client_id, None)

        if not symbol_clients:
            self.clients.pop(symbol, None)

        print(f"Client disconnected: {client_id} from {symbol}")

    async def broadcast(self, message: dict):
        dead_clients = []

        for symbol, symbol_clients in self.clients.items():
            for client_id, websocket in symbol_clients.items():
                try:
                    await websocket.send_json(message)
                except Exception:
                    dead_clients.append((client_id, symbol))

        for client_id, symbol in dead_clients:
            self.disconnect(client_id, symbol)
