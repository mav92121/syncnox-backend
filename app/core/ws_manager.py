"""
WebSocket Connection Manager for real-time driver ↔ dispatch communication.

Two separate registries:
  - driver_connections: driver_id → WebSocket  (one mobile app per driver)
  - dispatch_connections: tenant_id → set[WebSocket]  (web app, supports multiple tabs)

Phase 1: In-process dict (single uvicorn worker).
Phase 2 upgrade path: replace the dicts with Redis pub/sub — all callers stay identical.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # driver_id → active WebSocket connection
        self.driver_connections: dict[int, WebSocket] = {}
        # tenant_id → set of WebSocket connections (multiple browser tabs)
        self.dispatch_connections: dict[int, set[WebSocket]] = defaultdict(set)

    # ------------------------------------------------------------------ #
    # Driver connections (mobile app)
    # ------------------------------------------------------------------ #

    async def connect_driver(self, driver_id: int, ws: WebSocket) -> None:
        await ws.accept()
        # Disconnect any existing stale connection for this driver
        if driver_id in self.driver_connections:
            try:
                await self.driver_connections[driver_id].close()
            except Exception:
                pass
        self.driver_connections[driver_id] = ws
        logger.info(f"Driver {driver_id} connected via WebSocket")

    def disconnect_driver(self, driver_id: int) -> None:
        self.driver_connections.pop(driver_id, None)
        logger.info(f"Driver {driver_id} disconnected from WebSocket")

    async def send_to_driver(self, driver_id: int, payload: dict[str, Any]) -> bool:
        """Send a JSON payload to a specific driver. Returns True if delivered."""
        ws = self.driver_connections.get(driver_id)
        if ws:
            try:
                await ws.send_json(payload)
                return True
            except Exception as e:
                logger.warning(f"Failed to send to driver {driver_id}: {e}")
                self.disconnect_driver(driver_id)
        return False

    # ------------------------------------------------------------------ #
    # Dispatch connections (web app)
    # ------------------------------------------------------------------ #

    async def connect_dispatch(self, tenant_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.dispatch_connections[tenant_id].add(ws)
        logger.info(f"Dispatch tab connected for tenant {tenant_id} (total: {len(self.dispatch_connections[tenant_id])})")

    def disconnect_dispatch(self, tenant_id: int, ws: WebSocket) -> None:
        self.dispatch_connections[tenant_id].discard(ws)
        logger.info(f"Dispatch tab disconnected for tenant {tenant_id}")

    async def broadcast_to_dispatch(self, tenant_id: int, payload: dict[str, Any]) -> int:
        """Broadcast a JSON payload to all web app tabs for a tenant. Returns delivery count."""
        connections = list(self.dispatch_connections.get(tenant_id, []))
        delivered = 0
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(payload)
                delivered += 1
            except Exception as e:
                logger.warning(f"Failed to send to dispatch tenant {tenant_id}: {e}")
                dead.append(ws)
        for ws in dead:
            self.dispatch_connections[tenant_id].discard(ws)
        return delivered

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #

    def is_driver_online(self, driver_id: int) -> bool:
        return driver_id in self.driver_connections

    def online_drivers(self, driver_ids: list[int]) -> list[int]:
        return [d for d in driver_ids if d in self.driver_connections]


# Singleton — imported everywhere
ws_manager = ConnectionManager()
