"""WebSocket manager for real-time task progress updates."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import WebSocket


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    OK = "OK"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"


@dataclass
class TaskProgress:
    """Task progress information."""
    task_id: str
    action: str
    status: TaskStatus
    progress: int = 0
    total_steps: int = 0
    step_name: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""
    started_at: str = ""
    ended_at: str = ""
    return_code: int | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WebSocketManager:
    """Manage WebSocket connections and broadcast task progress."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._tasks: dict[str, TaskProgress] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self._connections[client_id] = websocket

        # Send current task states to new connection
        for task in self._tasks.values():
            await self._send(websocket, task.to_dict())

    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        self._connections.pop(client_id, None)

    async def broadcast(self, data: dict[str, Any]):
        """Broadcast data to all connected clients."""
        disconnected = []
        for client_id, ws in self._connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self._connections.pop(client_id, None)

    async def _send(self, websocket: WebSocket, data: dict[str, Any]):
        """Send data to a specific WebSocket."""
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    def create_task(self, task_id: str, action: str) -> TaskProgress:
        """Create a new task and return its progress object."""
        now = datetime.now(UTC).isoformat()
        progress = TaskProgress(
            task_id=task_id,
            action=action,
            status=TaskStatus.PENDING,
            started_at=now,
            timestamp=now,
        )
        self._tasks[task_id] = progress
        return progress

    async def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        progress: int | None = None,
        step_name: str | None = None,
        stdout_tail: str | None = None,
        stderr_tail: str | None = None,
        return_code: int | None = None,
    ):
        """Update task progress and broadcast to all clients."""
        task = self._tasks.get(task_id)
        if not task:
            return

        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if step_name is not None:
            task.step_name = step_name
        if stdout_tail is not None:
            task.stdout_tail = stdout_tail
        if stderr_tail is not None:
            task.stderr_tail = stderr_tail
        if return_code is not None:
            task.return_code = return_code

        task.timestamp = datetime.now(UTC).isoformat()

        if status in (TaskStatus.OK, TaskStatus.FAIL, TaskStatus.TIMEOUT):
            task.ended_at = task.timestamp

        # Broadcast update
        await self.broadcast(task.to_dict())

    def get_task(self, task_id: str) -> TaskProgress | None:
        """Get task progress by ID."""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[TaskProgress]:
        """Get all tasks."""
        return list(self._tasks.values())


# Global WebSocket manager instance
ws_manager = WebSocketManager()
