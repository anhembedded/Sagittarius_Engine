import asyncio
import json
import logging
import sys
import threading
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

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
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9999,
        auth_token: str | None = None,
    ):
        """
        @param auth_token If set, a connecting client must supply a matching
        `?token=...` query parameter or the connection is rejected before any
        telemetry is sent. `None` (the default) accepts any client — set this
        explicitly for any deployment reachable beyond localhost.
        """
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.clients: set[Any] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger("WebsocketBroadcaster")
        self._server = None
        # Set once the server is actually bound and listening — lets a
        # caller (or a test) wait deterministically instead of guessing with
        # a sleep, and lets port=0 (ephemeral port) be resolved afterwards.
        self._ready_event = threading.Event()

        # Callback to fetch initial state for new clients
        self.on_new_client_callback: Callable[[], dict[str, Any]] | None = None

    def _extract_token(self, websocket: Any, legacy_path: str | None) -> str | None:
        # New (websockets.asyncio) API exposes the handshake request on the
        # connection object; the legacy API instead passes path as a second
        # positional argument to the handler.
        raw_path = legacy_path
        if raw_path is None:
            request = getattr(websocket, "request", None)
            raw_path = getattr(request, "path", None) if request is not None else None
        if not raw_path:
            return None
        query = urlparse(raw_path).query
        values = parse_qs(query).get("token")
        return values[0] if values else None

    async def _handler(self, websocket, *args, **kwargs):
        if self.auth_token is not None:
            legacy_path = args[0] if args else None
            token = self._extract_token(websocket, legacy_path)
            if token != self.auth_token:
                self._logger.warning(
                    f"Rejected websocket connection from {getattr(websocket, 'remote_address', '?')}: "
                    "missing or invalid token"
                )
                await websocket.close(code=4401, reason="Unauthorized")
                return

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
                    async with serve(self._handler, self.host, self.port) as server:
                        self._resolve_bound_port(server)
                        self._logger.info(
                            f"Websocket Broadcaster (asyncio) listening on ws://{self.host}:{self.port}"
                        )
                        self._ready_event.set()
                        await self._stop_event.wait()
                else:
                    start_server = serve(self._handler, self.host, self.port)
                    self._server = await start_server
                    self._resolve_bound_port(self._server)
                    self._logger.info(
                        f"Websocket Broadcaster (legacy) listening on ws://{self.host}:{self.port}"
                    )
                    self._ready_event.set()
                    await self._stop_event.wait()
            except asyncio.CancelledError:
                pass

        try:
            self._loop.run_until_complete(main())
        finally:
            self._loop.close()

    def _resolve_bound_port(self, server: Any) -> None:
        """@brief After binding, resolve the actual port — needed when
        `port=0` (ephemeral port) was requested, e.g. in tests."""
        sockets = getattr(server, "sockets", None)
        if sockets:
            self.port = sockets[0].getsockname()[1]

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._ready_event.clear()
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
