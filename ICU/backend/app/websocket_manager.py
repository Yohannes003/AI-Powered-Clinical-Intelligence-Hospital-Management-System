"""
WebSocket connection manager for real-time vital sign streaming.
Handles multiple client connections and broadcasts vital updates.
"""

import json
import asyncio
import logging
from typing import List, Dict, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        # Active connections: patient_id -> set of websockets
        self.patient_connections: Dict[int, Set[WebSocket]] = {}
        # Dashboard connections (receive all patient updates)
        self.dashboard_connections: Set[WebSocket] = set()
        # All active connections for health monitoring
        self.all_connections: Set[WebSocket] = set()

    async def connect_dashboard(self, websocket: WebSocket):
        """Accept a dashboard connection that receives all updates."""
        await websocket.accept()
        self.dashboard_connections.add(websocket)
        self.all_connections.add(websocket)
        logger.info(f"Dashboard connected. Total dashboards: {len(self.dashboard_connections)}")

        # Send connection confirmation
        await self.send_personal_message({
            "type": "connected",
            "data": {"message": "Connected to ICU monitoring stream", "role": "dashboard"},
            "timestamp": datetime.now().isoformat()
        }, websocket)

    async def connect_patient(self, websocket: WebSocket, patient_id: int):
        """Accept a connection for a specific patient's vitals."""
        await websocket.accept()
        if patient_id not in self.patient_connections:
            self.patient_connections[patient_id] = set()
        self.patient_connections[patient_id].add(websocket)
        self.all_connections.add(websocket)
        logger.info(f"Patient {patient_id} monitor connected. Total for patient: {len(self.patient_connections[patient_id])}")

        await self.send_personal_message({
            "type": "connected",
            "data": {"message": f"Monitoring patient {patient_id}", "patient_id": patient_id},
            "timestamp": datetime.now().isoformat()
        }, websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        self.dashboard_connections.discard(websocket)
        self.all_connections.discard(websocket)

        # Remove from patient-specific connections
        empty_patients = []
        for patient_id, connections in self.patient_connections.items():
            connections.discard(websocket)
            if not connections:
                empty_patients.append(patient_id)

        # Clean up empty patient connection sets
        for patient_id in empty_patients:
            del self.patient_connections[patient_id]

        logger.info(f"WebSocket disconnected. Remaining connections: {len(self.all_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast_to_dashboards(self, message: dict):
        """Broadcast a message to all dashboard connections."""
        disconnected = []
        for connection in self.dashboard_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to dashboard: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_to_patient(self, patient_id: int, message: dict):
        """Broadcast a message to all connections monitoring a specific patient."""
        if patient_id not in self.patient_connections:
            return

        disconnected = []
        for connection in self.patient_connections[patient_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to patient {patient_id}: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_vital_update(self, vital_data: dict):
        """
        Broadcast vital update to both dashboards and patient-specific connections.
        This is the main method used by the simulator to stream vitals.
        """
        message = {
            "type": "vital_update",
            "data": vital_data,
            "timestamp": datetime.now().isoformat()
        }

        # Broadcast to dashboards
        await self.broadcast_to_dashboards(message)

        # Broadcast to patient-specific connections
        patient_id = vital_data.get("patient_id")
        if patient_id:
            await self.broadcast_to_patient(patient_id, message)

    async def broadcast_alert(self, alert_data: dict):
        """Broadcast an alert to all connected dashboards."""
        message = {
            "type": "alert",
            "data": alert_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_dashboards(message)

        # Also send to patient-specific connections
        patient_id = alert_data.get("patient_id")
        if patient_id:
            await self.broadcast_to_patient(patient_id, message)

    async def broadcast_patient_update(self, patient_data: dict):
        """Broadcast patient status updates (admission, discharge, status change)."""
        message = {
            "type": "patient_update",
            "data": patient_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_dashboards(message)

    def get_connection_stats(self) -> dict:
        """Get current connection statistics."""
        return {
            "dashboard_connections": len(self.dashboard_connections),
            "patient_connections": {
                pid: len(conns) for pid, conns in self.patient_connections.items()
            },
            "total_connections": len(self.all_connections)
        }


# Singleton instance
manager = ConnectionManager()
