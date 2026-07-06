import asyncio
from dataclasses import dataclass, field
from typing import Callable

from fastapi import WebSocket

from app.metrics import record_websocket_message_sent


MAX_QUEUE_DEPTH = 200
WARN_QUEUE_DEPTH = 120


@dataclass
class ClientConnection:
    client_id: str
    symbol: str
    websocket: WebSocket
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=MAX_QUEUE_DEPTH))
    mode: str = "delta"
    dropped_messages: int = 0
    sender_task: asyncio.Task | None = None

    def start_sender(
        self,
        on_dead_client: Callable[[str, str], None],
        on_queue_depth_change: Callable[[str, str, int], None],
    ):
        self.sender_task = asyncio.create_task(
            self._sender_loop(on_dead_client, on_queue_depth_change)
        )

    async def _sender_loop(
        self,
        on_dead_client: Callable[[str, str], None],
        on_queue_depth_change: Callable[[str, str, int], None],
    ):
        try:
            while True:
                message = await self.queue.get()
                await self.websocket.send_json(message)
                record_websocket_message_sent(self.symbol, message.get("type", "unknown"))
                self.queue.task_done()
                on_queue_depth_change(self.symbol, self.client_id, self.queue_depth())
        except asyncio.CancelledError:
            raise
        except Exception:
            on_dead_client(self.client_id, self.symbol)

    def enqueue(self, message: dict) -> bool:
        if self.queue.full():
            self.dropped_messages += 1
            self.mode = "snapshot"
            self._clear_queue()

            self.queue.put_nowait({
                "type": "resync_required",
                "symbol": self.symbol,
                "reason": "client_backpressure",
                "dropped_messages": self.dropped_messages,
            })
            return False

        self.mode = "delta"
        self.queue.put_nowait(message)
        return True

    def stop(self):
        if self.sender_task:
            self.sender_task.cancel()

    def queue_depth(self) -> int:
        return self.queue.qsize()

    def is_warning(self) -> bool:
        return self.queue.qsize() >= WARN_QUEUE_DEPTH

    def _clear_queue(self):
        while not self.queue.empty():
            self.queue.get_nowait()
            self.queue.task_done()
