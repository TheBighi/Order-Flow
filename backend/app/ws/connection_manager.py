import asyncio
from fastapi import WebSocket

from app.metrics import set_connected_clients


class ConnectionManager:
    def __init__(self):
        self.clients: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, client_id: str, symbol: str, websocket: WebSocket):
        await websocket.accept()

        symbol = symbol.upper()

        if symbol not in self.clients:  # { symbol: { "conn_idx1" : websocket_obj, "conn_idx2": websocket_obj } }
            self.clients[symbol] = {}

        self.clients[symbol][client_id] = websocket
        set_connected_clients(symbol, len(self.clients[symbol]))

        print(f"Client connected: {client_id} watching {symbol}")

    def disconnect(self, client_id: str, symbol: str):
        symbol = symbol.upper()
        symbol_clients = self.clients.get(symbol)

        if not symbol_clients:
            return

        symbol_clients.pop(client_id, None)
        remaining_clients = len(symbol_clients)

        if not symbol_clients:
            self.clients.pop(symbol, None)

        set_connected_clients(symbol, remaining_clients)
        print(f"Client disconnected: {client_id} from {symbol}")

    async def broadcast_to_symbol(self, symbol: str, message: dict):
        symbol = symbol.upper()
        symbol_clients = self.clients.get(symbol)

        if not symbol_clients:
            return

        dead_clients = []

        clients = list(symbol_clients.items())

        tasks = [ws.send_json(message) for _, ws in clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (client_id, _), result in zip(clients, results):
            if isinstance(result, Exception):
                dead_clients.append((client_id, symbol))

        for client_id, symbol in dead_clients:
            self.disconnect(client_id, symbol)
