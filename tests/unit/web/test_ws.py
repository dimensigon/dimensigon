"""Tests for WebSocket execution monitoring infrastructure."""
import importlib
import json
import sys
from unittest import TestCase, mock

# Patch netifaces before importing dimensigon modules
if 'netifaces' not in sys.modules:
    mock_netifaces = mock.MagicMock()
    mock_netifaces.interfaces.return_value = ['lo']
    mock_netifaces.ifaddresses.return_value = {2: [{'addr': '127.0.0.1'}]}
    mock_netifaces.AF_INET = 2
    sys.modules['netifaces'] = mock_netifaces

from dimensigon.web.admin.ws import (
    ConnectionManager, ExecutionEvent,
    emit_step_started, emit_step_completed, emit_orch_completed,
    request_cancel, is_cancelled, clear_cancel, ws_manager,
)


class MockWebSocket:
    """Mock WebSocket for testing broadcasts."""

    def __init__(self):
        self.messages = []
        self.closed = False

    def send(self, data):
        if self.closed:
            raise ConnectionError("WebSocket closed")
        self.messages.append(json.loads(data))


class TestConnectionManager(TestCase):

    def setUp(self):
        self.cm = ConnectionManager()

    def test_connect_and_disconnect(self):
        ws = MockWebSocket()
        self.cm.connect('exec-1', ws)
        self.assertEqual(1, self.cm.get_viewer_count('exec-1'))
        self.assertTrue(self.cm.has_viewers('exec-1'))

        self.cm.disconnect('exec-1', ws)
        self.assertEqual(0, self.cm.get_viewer_count('exec-1'))
        self.assertFalse(self.cm.has_viewers('exec-1'))

    def test_broadcast(self):
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        self.cm.connect('exec-1', ws1)
        self.cm.connect('exec-1', ws2)

        event = ExecutionEvent(ExecutionEvent.STEP_STARTED, 'exec-1', {'step': 'test'})
        self.cm.broadcast(event)

        self.assertEqual(1, len(ws1.messages))
        self.assertEqual(1, len(ws2.messages))
        self.assertEqual('step_started', ws1.messages[0]['type'])
        self.assertEqual('exec-1', ws1.messages[0]['execution_id'])

    def test_broadcast_no_viewers(self):
        """Broadcast to execution with no viewers should not error."""
        event = ExecutionEvent(ExecutionEvent.STEP_STARTED, 'nobody', {})
        self.cm.broadcast(event)  # Should not raise

    def test_dead_connection_cleanup(self):
        """Dead connections should be cleaned up on broadcast."""
        ws_alive = MockWebSocket()
        ws_dead = MockWebSocket()
        ws_dead.closed = True

        self.cm.connect('exec-1', ws_alive)
        self.cm.connect('exec-1', ws_dead)
        self.assertEqual(2, self.cm.get_viewer_count('exec-1'))

        event = ExecutionEvent(ExecutionEvent.STEP_COMPLETED, 'exec-1', {})
        self.cm.broadcast(event)

        # Dead connection removed
        self.assertEqual(1, self.cm.get_viewer_count('exec-1'))
        self.assertEqual(1, len(ws_alive.messages))

    def test_multiple_executions(self):
        """Viewers of different executions are independent."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        self.cm.connect('exec-1', ws1)
        self.cm.connect('exec-2', ws2)

        event = ExecutionEvent(ExecutionEvent.STEP_STARTED, 'exec-1', {})
        self.cm.broadcast(event)

        self.assertEqual(1, len(ws1.messages))
        self.assertEqual(0, len(ws2.messages))


class TestExecutionEvent(TestCase):

    def test_to_json(self):
        event = ExecutionEvent('test_type', 'exec-123', {'key': 'value'})
        data = json.loads(event.to_json())
        self.assertEqual('test_type', data['type'])
        self.assertEqual('exec-123', data['execution_id'])
        self.assertEqual('value', data['data']['key'])
        self.assertIn('timestamp', data)


class TestCancellation(TestCase):

    def tearDown(self):
        clear_cancel('test-exec')

    def test_cancel_and_check(self):
        self.assertFalse(is_cancelled('test-exec'))
        request_cancel('test-exec')
        self.assertTrue(is_cancelled('test-exec'))

    def test_clear_cancel(self):
        request_cancel('test-exec')
        clear_cancel('test-exec')
        self.assertFalse(is_cancelled('test-exec'))


class TestEmitHelpers(TestCase):

    def test_emit_step_started(self):
        """emit_step_started broadcasts to ws_manager."""
        ws = MockWebSocket()
        ws_manager.connect('exec-1', ws)
        try:
            emit_step_started('exec-1', 'se-1', 'step-1', 'My Step', 'srv-1', 'server1')
            self.assertEqual(1, len(ws.messages))
            self.assertEqual('step_started', ws.messages[0]['type'])
            self.assertEqual('My Step', ws.messages[0]['data']['step_name'])
        finally:
            ws_manager.disconnect('exec-1', ws)

    def test_emit_step_completed(self):
        ws = MockWebSocket()
        ws_manager.connect('exec-1', ws)
        try:
            emit_step_completed('exec-1', 'se-1', 'step-1', True, rc=0,
                               stdout='output', stderr='', elapsed=1.5)
            self.assertEqual(1, len(ws.messages))
            self.assertEqual('step_completed', ws.messages[0]['type'])
            self.assertTrue(ws.messages[0]['data']['success'])
        finally:
            ws_manager.disconnect('exec-1', ws)

    def test_emit_orch_completed(self):
        ws = MockWebSocket()
        ws_manager.connect('exec-1', ws)
        try:
            emit_orch_completed('exec-1', True, 'All good')
            self.assertEqual(1, len(ws.messages))
            self.assertEqual('orch_completed', ws.messages[0]['type'])
        finally:
            ws_manager.disconnect('exec-1', ws)
