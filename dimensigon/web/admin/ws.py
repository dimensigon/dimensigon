"""
WebSocket handler for real-time execution monitoring.

Manages active viewer connections per execution and broadcasts
step execution state changes in real time.
"""
import json
import logging
import threading
import time
import typing as t

_LOGGER = logging.getLogger('dm.ws')


class ExecutionEvent:
    """An event emitted during execution lifecycle."""

    STEP_STARTED = 'step_started'
    STEP_COMPLETED = 'step_completed'
    STEP_FAILED = 'step_failed'
    ORCH_STARTED = 'orch_started'
    ORCH_COMPLETED = 'orch_completed'
    ORCH_CANCELLED = 'orch_cancelled'

    def __init__(self, event_type: str, execution_id: str, data: dict = None):
        self.event_type = event_type
        self.execution_id = execution_id
        self.data = data or {}
        self.timestamp = time.time()

    def to_json(self) -> str:
        return json.dumps({
            'type': self.event_type,
            'execution_id': self.execution_id,
            'data': self.data,
            'timestamp': self.timestamp,
        })


class ConnectionManager:
    """Manages WebSocket connections for execution monitoring.

    Thread-safe connection tracking and event broadcasting.
    """

    def __init__(self):
        self._connections: t.Dict[str, t.Set] = {}  # execution_id -> set of ws connections
        self._lock = threading.Lock()

    def connect(self, execution_id: str, ws):
        """Register a WebSocket connection for an execution."""
        with self._lock:
            if execution_id not in self._connections:
                self._connections[execution_id] = set()
            self._connections[execution_id].add(ws)
            _LOGGER.debug(f"WS connected to execution {execution_id} "
                         f"({len(self._connections[execution_id])} viewers)")

    def disconnect(self, execution_id: str, ws):
        """Remove a WebSocket connection."""
        with self._lock:
            if execution_id in self._connections:
                self._connections[execution_id].discard(ws)
                if not self._connections[execution_id]:
                    del self._connections[execution_id]
                    _LOGGER.debug(f"No more viewers for execution {execution_id}")

    def broadcast(self, event: ExecutionEvent):
        """Send an event to all viewers of an execution."""
        with self._lock:
            connections = self._connections.get(event.execution_id, set()).copy()

        if not connections:
            return

        message = event.to_json()
        dead = []
        for ws in connections:
            try:
                ws.send(message)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        if dead:
            with self._lock:
                conns = self._connections.get(event.execution_id, set())
                for ws in dead:
                    conns.discard(ws)

    def get_viewer_count(self, execution_id: str) -> int:
        with self._lock:
            return len(self._connections.get(execution_id, set()))

    def has_viewers(self, execution_id: str) -> bool:
        with self._lock:
            return bool(self._connections.get(execution_id))


# Global connection manager instance
ws_manager = ConnectionManager()

# Cancellation flags: execution_id -> True
_cancel_flags: t.Dict[str, bool] = {}
_cancel_lock = threading.Lock()


def request_cancel(execution_id: str):
    """Set cancellation flag for an execution."""
    with _cancel_lock:
        _cancel_flags[execution_id] = True
    ws_manager.broadcast(ExecutionEvent(
        ExecutionEvent.ORCH_CANCELLED,
        execution_id,
        {'message': 'Cancellation requested'}
    ))


def is_cancelled(execution_id: str) -> bool:
    """Check if an execution has been cancelled."""
    with _cancel_lock:
        return _cancel_flags.get(execution_id, False)


def clear_cancel(execution_id: str):
    """Clear cancellation flag after execution ends."""
    with _cancel_lock:
        _cancel_flags.pop(execution_id, None)


def emit_step_started(execution_id: str, step_execution_id: str,
                      step_id: str, step_name: str, server_id: str, server_name: str):
    """Emit event when a step starts executing."""
    ws_manager.broadcast(ExecutionEvent(
        ExecutionEvent.STEP_STARTED,
        execution_id,
        {
            'step_execution_id': step_execution_id,
            'step_id': step_id,
            'step_name': step_name,
            'server_id': server_id,
            'server_name': server_name,
            'start_time': time.time(),
        }
    ))


def emit_step_completed(execution_id: str, step_execution_id: str,
                        step_id: str, success: bool, rc: int = None,
                        stdout: str = None, stderr: str = None,
                        elapsed: float = None):
    """Emit event when a step completes."""
    event_type = ExecutionEvent.STEP_COMPLETED if success else ExecutionEvent.STEP_FAILED
    ws_manager.broadcast(ExecutionEvent(
        event_type,
        execution_id,
        {
            'step_execution_id': step_execution_id,
            'step_id': step_id,
            'success': success,
            'rc': rc,
            'stdout': stdout,
            'stderr': stderr,
            'elapsed': elapsed,
            'end_time': time.time(),
        }
    ))


def emit_orch_started(execution_id: str, orchestration_name: str, target: dict = None):
    """Emit event when an orchestration starts."""
    ws_manager.broadcast(ExecutionEvent(
        ExecutionEvent.ORCH_STARTED,
        execution_id,
        {
            'orchestration_name': orchestration_name,
            'target': target,
        }
    ))


def emit_orch_completed(execution_id: str, success: bool, message: str = None):
    """Emit event when an orchestration completes."""
    ws_manager.broadcast(ExecutionEvent(
        ExecutionEvent.ORCH_COMPLETED,
        execution_id,
        {
            'success': success,
            'message': message,
        }
    ))
    clear_cancel(execution_id)
