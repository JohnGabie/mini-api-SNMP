import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("mini_api_snmp.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"WS client connected — total: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info(f"WS client disconnected — total: {len(self._connections)}")

    async def broadcast(self, event: str, **data: Any) -> None:
        if not self._connections:
            return

        payload = json.dumps({
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        })

        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.remove(ws)

    @property
    def active_connections(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()
