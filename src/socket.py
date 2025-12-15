from contextlib import suppress
from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self, app_channel: str = "global"):
        self.app_channel = app_channel
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str | None = None):
        await websocket.accept()
        #
        if not isinstance(channel, str):
            channel = self.app_channel
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        #
        self.active_connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str | None = None):
        if not isinstance(channel, str):
            channel = self.app_channel
        with suppress(KeyError, ValueError):
            self.active_connections[channel].remove(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]

    async def broadcast(self, message: str, channel: str | None = None):
        if not isinstance(channel, str):
            channel = self.app_channel
        for connection in self.active_connections.get(channel, []):
            with suppress(Exception):
                await connection.send_text(str(message))


manager = ConnectionManager()
