from unittest import TestCase, mock

from tests.base import OneNodeMixin


class TestRoutes(OneNodeMixin, TestCase):

    @mock.patch('dimensigon.web.routes.current_app')
    def test_healthcheck(self, mock_current_app):
        mock_current_app.dm.cluster_manager.get_alive.return_value = []
        mock_current_app.dm.cluster_manager.get_zombies.return_value = []
        response = self.client.get('/healthcheck')
        self.assertEqual(200, response.status_code)
