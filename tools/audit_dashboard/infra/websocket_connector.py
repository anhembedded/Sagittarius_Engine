import json
import logging
from collections.abc import Callable
from typing import Any

from Domain.ports import IRealtimeConnector
from PySide6.QtCore import QUrl
from PySide6.QtWebSockets import QWebSocket


class WebsocketConnector(IRealtimeConnector):
    def __init__(self, url: str = "ws://127.0.0.1:9999"):
        self.url = url
        self.socket = QWebSocket()
        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.textMessageReceived.connect(self._on_text_message_received)
        self.socket.errorOccurred.connect(self._on_error)
        self._callback: Callable[[Any], None] | None = None
        self._logger = logging.getLogger("WebsocketConnector")

    def connect(self) -> None:
        self._logger.info(f"Connecting to {self.url}...")
        self.socket.open(QUrl(self.url))

    def disconnect(self) -> None:
        self._logger.info("Disconnecting...")
        self.socket.close()

    def on_message_received(self, callback: Callable[[Any], None]) -> None:
        self._callback = callback

    def _on_connected(self):
        self._logger.info("Connected to websocket server.")

    def _on_disconnected(self):
        self._logger.info("Disconnected from websocket server.")

    def _on_text_message_received(self, message: str):
        try:
            payload = json.loads(message)
            if self._callback:
                self._callback(payload)
        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse websocket message: {e}")

    def _on_error(self, error):
        self._logger.error(f"Websocket error: {error}")
