import asyncio
import json
import logging
import sys
import threading
from collections.abc import Callable
from typing import Any

from ..ports import ITelemetryBroadcaster

try:
    try:
        from websockets.asyncio.server import serve
    except ImportError:
        from websockets.server import serve
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class WebsocketBroadcaster(ITelemetryBroadcaster):
    def __init__(self, host: str = "127.0.0.1", port: int = 9999):
        self.host = host
        self.port = port
        self.clients: set[Any] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger("WebsocketBroadcaster")
        self._server = None

        # Callback to fetch initial state for new clients
        self.on_new_client_callback: Callable[[], dict[str, Any]] | None = None

    async def _handler(self, websocket, *args, **kwargs):
        self.clients.add(websocket)
        self._logger.info(f"New client connected: {websocket.remote_address}")

        if self.on_new_client_callback:
            try:
                initial_state = self.on_new_client_callback()
                payload = json.dumps({"event": "initial_state", "data": initial_state})
                await websocket.send(payload)
            except Exception as e:
                self._logger.error(f"Error sending initial state: {e}")

        try:
            # Keep the connection open
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)
            self._logger.info(f"Client disconnected: {websocket.remote_address}")

    def _run_server(self):
        if not WEBSOCKETS_AVAILABLE:
            self._logger.error("websockets library not installed. Please install it.")
            return

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._stop_event = asyncio.Event()

        async def main():
            try:
                if "websockets.asyncio" in sys.modules:
                    async with serve(self._handler, self.host, self.port):
                        self._logger.info(
                            f"Websocket Broadcaster (asyncio) listening on ws://{self.host}:{self.port}"
                        )
                        await self._stop_event.wait()
                else:
                    start_server = serve(self._handler, self.host, self.port)
                    self._server = await start_server
                    self._logger.info(
                        f"Websocket Broadcaster (legacy) listening on ws://{self.host}:{self.port}"
                    )
                    await self._stop_event.wait()
            except asyncio.CancelledError:
                pass

        try:
            self._loop.run_until_complete(main())
        finally:
            self._loop.close()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)

        if self._thread:
            self._thread.join(timeout=2.0)

    def broadcast(self, event_name: str, payload: dict[str, Any]) -> None:
        if not self._loop or not self.clients:
            return

        message = json.dumps({"event": event_name, "data": payload})

        async def _broadcast():
            if not self.clients:
                return
            tasks = [
                asyncio.create_task(client.send(message)) for client in self.clients
            ]
            done, pending = await asyncio.wait(tasks, timeout=1.0)
            for t in pending:
                t.cancel()

        asyncio.run_coroutine_threadsafe(_broadcast(), self._loop)
