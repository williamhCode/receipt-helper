# src/websocket_manager.py

from typing import Dict, List, Set
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # group_id -> set of websockets
        self.group_connections: Dict[int, Set[WebSocket]] = {}
        # websocket -> group_id mapping for cleanup
        self.websocket_to_group: Dict[WebSocket, int] = {}

    async def connect(self, websocket: WebSocket, group_id: int):
        """Accept a new WebSocket connection and add to group"""
        await websocket.accept()
        
        # Initialize group if doesn't exist
        if group_id not in self.group_connections:
            self.group_connections[group_id] = set()
        
        # Add connection to group
        self.group_connections[group_id].add(websocket)
        self.websocket_to_group[websocket] = group_id
        
        logger.info(f"Client connected to group {group_id}. Total connections: {len(self.group_connections[group_id])}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.websocket_to_group:
            group_id = self.websocket_to_group[websocket]
            
            # Remove from group
            if group_id in self.group_connections:
                self.group_connections[group_id].discard(websocket)
                
                # Clean up empty groups
                if not self.group_connections[group_id]:
                    del self.group_connections[group_id]
            
            # Remove from mapping
            del self.websocket_to_group[websocket]
            
            logger.info(f"Client disconnected from group {group_id}")

    async def broadcast_to_group(self, group_id: int, message: dict, exclude_websocket: WebSocket | None = None):
        """Send a message to all connections in a group, optionally excluding one"""
        if group_id not in self.group_connections:
            return
        
        # Create a copy of the set to avoid modification during iteration
        connections = self.group_connections[group_id].copy()
        disconnected = []
        
        for websocket in connections:
            if exclude_websocket and websocket == exclude_websocket:
                continue
                
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to websocket: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            await self.disconnect(websocket)

    async def send_to_websocket(self, websocket: WebSocket, message: dict):
        """Send a message to a specific websocket"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to websocket: {e}")
            await self.disconnect(websocket)

    def get_group_connection_count(self, group_id: int) -> int:
        """Get the number of active connections for a group"""
        return len(self.group_connections.get(group_id, set()))

# Global connection manager instance
connection_manager = ConnectionManager()
