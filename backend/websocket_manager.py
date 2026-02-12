import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections to clients."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            self._connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self._connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self._connections:
            return

        message_json = json.dumps(message)

        # Snapshot connections under lock, then send outside lock
        async with self._lock:
            connections = set(self._connections)

        dead_connections = set()
        for connection in connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.add(connection)

        # Re-acquire lock to remove dead connections
        if dead_connections:
            async with self._lock:
                self._connections -= dead_connections

    async def send_state_update(self, connected: bool, flight_state: dict | None,
                                 checklist_state: dict, auto_transition: bool = True,
                                 flight_plan: dict | None = None):
        """Send a state update to all clients."""
        message = {
            "type": "state_update",
            "data": {
                "connected": connected,
                "flight_state": flight_state,
                "auto_transition": auto_transition,
                "flight_plan": flight_plan,
                **checklist_state,
            }
        }
        await self.broadcast(message)

    @property
    def connection_count(self) -> int:
        return len(self._connections)
