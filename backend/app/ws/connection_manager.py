from fastapi import WebSocket

from app.metrics import (
    clear_backpressure_queue_depth,
    record_backpressure_event,
    set_backpressure_clients,
    set_backpressure_queue_depth,
    set_connected_clients,
)
from app.ws.backpressure import ClientConnection


class ConnectionManager:
    def __init__(self):
        self.clients: dict[str, dict[str, ClientConnection]] = {}

    async def connect(self, client_id: str, symbol: str, websocket: WebSocket):
        await websocket.accept()

        symbol = symbol.upper()

        if symbol not in self.clients:  # { symbol: { "conn_idx1" : websocket_obj, "conn_idx2": websocket_obj } }
            self.clients[symbol] = {}

        client = ClientConnection(client_id=client_id, symbol=symbol, websocket=websocket)
        client.start_sender(self.disconnect, self._set_queue_depth)

        self.clients[symbol][client_id] = client
        set_connected_clients(symbol, len(self.clients[symbol]))
        set_backpressure_queue_depth(symbol, client_id, 0)
        self._update_backpressure_clients(symbol)

        print(f"Client connected: {client_id} watching {symbol}")

    def disconnect(self, client_id: str, symbol: str):
        symbol = symbol.upper()
        symbol_clients = self.clients.get(symbol)

        if not symbol_clients:
            return

        client = symbol_clients.pop(client_id, None)

        if client:
            client.stop()
            clear_backpressure_queue_depth(symbol, client_id)

        remaining_clients = len(symbol_clients)

        if not symbol_clients:
            self.clients.pop(symbol, None)

        set_connected_clients(symbol, remaining_clients)
        self._update_backpressure_clients(symbol)
        print(f"Client disconnected: {client_id} from {symbol}")

    async def broadcast_to_symbol(self, symbol: str, message: dict):
        symbol = symbol.upper()
        symbol_clients = self.clients.get(symbol)

        if not symbol_clients:
            return

        clients = list(symbol_clients.items())

        for client_id, client in clients:
            queued = client.enqueue(message)
            set_backpressure_queue_depth(symbol, client_id, client.queue_depth())

            if not queued:
                record_backpressure_event(symbol)

        self._update_backpressure_clients(symbol)

    def _update_backpressure_clients(self, symbol: str):
        symbol = symbol.upper()
        symbol_clients = self.clients.get(symbol, {})
        warning_clients = sum(1 for client in symbol_clients.values() if client.is_warning())
        set_backpressure_clients(symbol, warning_clients)

    def _set_queue_depth(self, symbol: str, client_id: str, depth: int):
        set_backpressure_queue_depth(symbol, client_id, depth)
        self._update_backpressure_clients(symbol)
