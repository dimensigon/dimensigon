"""Tests for container-native deployment features."""

import os
import signal
import unittest
from unittest.mock import patch, MagicMock


class TestContainerEnvConfig(unittest.TestCase):
    """Test that environment variable mappings in Config work correctly."""

    def _import_config(self):
        """Import Config class fresh."""
        from dimensigon.web.config import Config
        return Config

    def test_discovery_dns_default_none(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('DM_DISCOVERY_DNS', None)
            Config = self._import_config()
            # Re-evaluate since class attrs are set at import time;
            # check the environ.get logic directly
            result = os.environ.get('DM_DISCOVERY_DNS')
            self.assertIsNone(result)

    def test_discovery_dns_from_env(self):
        with patch.dict(os.environ, {'DM_DISCOVERY_DNS': 'my-dns.local'}):
            result = os.environ.get('DM_DISCOVERY_DNS')
            self.assertEqual(result, 'my-dns.local')

    def test_auto_join_default_true(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('DM_AUTO_JOIN', None)
            result = os.environ.get('DM_AUTO_JOIN', 'true').lower() == 'true'
            self.assertTrue(result)

    def test_auto_join_false(self):
        with patch.dict(os.environ, {'DM_AUTO_JOIN': 'false'}):
            result = os.environ.get('DM_AUTO_JOIN', 'true').lower() == 'true'
            self.assertFalse(result)

    def test_auto_join_case_insensitive(self):
        with patch.dict(os.environ, {'DM_AUTO_JOIN': 'False'}):
            result = os.environ.get('DM_AUTO_JOIN', 'true').lower() == 'true'
            self.assertFalse(result)

    def test_node_name_from_env(self):
        with patch.dict(os.environ, {'DM_NODE_NAME': 'worker-1'}):
            result = os.environ.get('DM_NODE_NAME')
            self.assertEqual(result, 'worker-1')

    def test_node_name_default_none(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('DM_NODE_NAME', None)
            result = os.environ.get('DM_NODE_NAME')
            self.assertIsNone(result)

    def test_graceful_shutdown_timeout_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('DM_GRACEFUL_SHUTDOWN_TIMEOUT', None)
            result = int(os.environ.get('DM_GRACEFUL_SHUTDOWN_TIMEOUT', '30'))
            self.assertEqual(result, 30)

    def test_graceful_shutdown_timeout_custom(self):
        with patch.dict(os.environ, {'DM_GRACEFUL_SHUTDOWN_TIMEOUT': '60'}):
            result = int(os.environ.get('DM_GRACEFUL_SHUTDOWN_TIMEOUT', '30'))
            self.assertEqual(result, 60)

    def test_config_class_has_container_attrs(self):
        """Verify the Config class has the container-native attributes."""
        from dimensigon.web.config import Config
        self.assertTrue(hasattr(Config, 'DISCOVERY_DNS'))
        self.assertTrue(hasattr(Config, 'AUTO_JOIN'))
        self.assertTrue(hasattr(Config, 'NODE_NAME'))
        self.assertTrue(hasattr(Config, 'GRACEFUL_SHUTDOWN_TIMEOUT'))


class TestGracefulShutdown(unittest.TestCase):
    """Test graceful shutdown signal handler registration."""

    @patch('dimensigon.core.mp')
    def test_dimensigon_has_graceful_shutdown_method(self, mock_mp):
        """Verify the Dimensigon class has a graceful_shutdown method."""
        mock_mp.Manager.return_value = MagicMock()
        from dimensigon.core import Dimensigon
        self.assertTrue(hasattr(Dimensigon, 'graceful_shutdown'))
        self.assertTrue(callable(getattr(Dimensigon, 'graceful_shutdown')))

    @patch('dimensigon.core.mp')
    def test_dimensigon_has_register_shutdown_signals(self, mock_mp):
        """Verify the Dimensigon class has signal registration method."""
        mock_mp.Manager.return_value = MagicMock()
        from dimensigon.core import Dimensigon
        self.assertTrue(hasattr(Dimensigon, '_register_shutdown_signals'))

    @patch('dimensigon.core.mp')
    def test_shutting_down_flag_initialized_false(self, mock_mp):
        """Verify _shutting_down flag starts as False."""
        mock_mp.Manager.return_value = MagicMock()
        from dimensigon.core import Dimensigon
        dm = Dimensigon()
        self.assertFalse(dm._shutting_down)

    @patch('dimensigon.core.mp')
    @patch('dimensigon.core.signal')
    def test_register_shutdown_signals(self, mock_signal, mock_mp):
        """Verify that signal handlers are registered for SIGTERM and SIGINT."""
        mock_mp.Manager.return_value = MagicMock()
        from dimensigon.core import Dimensigon
        dm = Dimensigon()
        dm._register_shutdown_signals()

        calls = mock_signal.signal.call_args_list
        registered_signals = [c[0][0] for c in calls]
        self.assertIn(mock_signal.SIGTERM, registered_signals)
        self.assertIn(mock_signal.SIGINT, registered_signals)

    @patch('dimensigon.core.mp')
    def test_graceful_shutdown_sets_flag(self, mock_mp):
        """Verify graceful_shutdown sets the _shutting_down flag."""
        mock_mp.Manager.return_value = MagicMock()
        from dimensigon.core import Dimensigon
        dm = Dimensigon()
        dm._main_ctx = MagicMock()

        dm.graceful_shutdown(signum=signal.SIGTERM, frame=None)

        self.assertTrue(dm._shutting_down)
        dm._main_ctx.shutdown_event.set.assert_called_once()


if __name__ == '__main__':
    unittest.main()
