# src/websocket_manager.py

from fastapi import WebSocket
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.group_connections: dict[int, set[WebSocket]] = {}
        self.websocket_to_group: dict[WebSocket, int] = {}
        self.pending_broadcasts: dict[int, asyncio.Task | None] = {}
        self.buffer_delay = 2.0

    async def connect(self, websocket: WebSocket, group_id: int):
        await websocket.accept()

        if group_id not in self.group_connections:
            self.group_connections[group_id] = set()

        self.group_connections[group_id].add(websocket)
        self.websocket_to_group[websocket] = group_id

        logger.info(f"Client connected to group {group_id}. Total connections: {len(self.group_connections[group_id])}")

    async def disconnect(self, websocket: WebSocket):
        if websocket in self.websocket_to_group:
            group_id = self.websocket_to_group[websocket]

            if group_id in self.group_connections:
                self.group_connections[group_id].discard(websocket)

                if not self.group_connections[group_id]:
                    del self.group_connections[group_id]
                    if group_id in self.pending_broadcasts and self.pending_broadcasts[group_id]:
                        self.pending_broadcasts[group_id].cancel()  # pyright: ignore[reportOptionalMemberAccess]
                        del self.pending_broadcasts[group_id]

            # Remove from mapping
            del self.websocket_to_group[websocket]

            logger.info(f"Client disconnected from group {group_id}")

    async def _do_broadcast(self, group_id: int, message: dict, exclude_websocket: WebSocket | None = None):
        if group_id not in self.group_connections:
            return

        # Create a copy of the set to avoid modification during iteration
        connections = self.group_connections[group_id].copy()
        disconnected = []

        sent_count = 0
        for websocket in connections:
            if exclude_websocket and websocket == exclude_websocket:
                continue

            try:
                await websocket.send_text(json.dumps(message))
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending message to websocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket)

        logger.info(f"Broadcast to group {group_id}: sent to {sent_count} clients")

    async def broadcast_to_group_debounced(self, group_id: int, message: dict, exclude_websocket: WebSocket | None = None):
        if group_id not in self.group_connections:
            return

        # Count how many clients would receive this message
        connections = self.group_connections[group_id]
        recipient_count = len(connections)
        if exclude_websocket and exclude_websocket in connections:
            recipient_count -= 1

        # Don't broadcast if there are no other clients
        if recipient_count == 0:
            logger.info(f"Skipping broadcast to group {group_id}: no other clients connected")
            return

        # Cancel any existing pending broadcast for this group
        if group_id in self.pending_broadcasts and self.pending_broadcasts[group_id]:
            self.pending_broadcasts[group_id].cancel()  # pyright: ignore[reportOptionalMemberAccess]

        # Schedule a new broadcast after the buffer delay
        async def delayed_broadcast():
            try:
                await asyncio.sleep(self.buffer_delay)
                await self._do_broadcast(group_id, message, exclude_websocket)
            except asyncio.CancelledError:
                logger.info(f"Broadcast to group {group_id} was cancelled (replaced by newer update)")
            finally:
                if group_id in self.pending_broadcasts:
                    self.pending_broadcasts[group_id] = None

        # Store the task so we can cancel it if needed
        self.pending_broadcasts[group_id] = asyncio.create_task(delayed_broadcast())
        logger.info(f"Scheduled broadcast to group {group_id} in {self.buffer_delay}s (recipients: {recipient_count})")

    async def send_to_websocket(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to websocket: {e}")
            await self.disconnect(websocket)

    def get_group_connection_count(self, group_id: int) -> int:
        return len(self.group_connections.get(group_id, set()))


# Global connection manager instance
connection_manager = ConnectionManager()
