from unittest import TestCase
from unittest.mock import patch

from dm.domain.entities import Server, Route
from dm.web import create_app, db


class TestServer(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_route(self):
        dest = Server('dest', port=80)
        proxy = Server('proxy', port=80)

        r = Route(destination=dest)

        self.assertEqual(dest, r.destination)
        self.assertIsNone(r.proxy_server)
        self.assertEqual(dest.gates[0], r.gate)
        self.assertEqual(0, r.cost)

        # routes defined with a gate
        ## dest
        r = Route(destination=dest, gate=dest.gates[0])
        self.assertEqual(dest, r.destination)
        self.assertIsNone(r.proxy_server)
        self.assertEqual(dest.gates[0], r.gate)
        self.assertEqual(0, r.cost)

        r = Route(destination=dest, gate=dest.gates[0], cost=0)
        self.assertEqual(dest, r.destination)
        self.assertIsNone(r.proxy_server)
        self.assertEqual(dest.gates[0], r.gate)
        self.assertEqual(0, r.cost)

        with self.assertRaises(ValueError):
            r = Route(destination=dest, gate=dest.gates[0], cost=1)

        ## proxy
        with self.assertRaises(ValueError):
            Route(destination=dest, gate=proxy.gates[0])

        with self.assertRaises(ValueError):
            Route(destination=dest, gate=proxy.gates[0], cost=0)

        r = Route(destination=dest, gate=proxy.gates[0], cost=1)
        self.assertEqual(dest, r.destination)
        self.assertIsNone(r.proxy_server)
        self.assertEqual(proxy.gates[0], r.gate)
        self.assertEqual(1, r.cost)

        # routes defined with a proxy server
        ## dest
        r = Route(destination=dest, proxy_server=dest)
        self.assertEqual(dest, r.destination)
        self.assertIsNone(r.proxy_server)
        self.assertEqual(dest.gates[0], r.gate)
        self.assertEqual(0, r.cost)

        r = Route(destination=dest, proxy_server=dest, cost=0)
        self.assertEqual(dest, r.destination)
        self.assertIsNone(r.proxy_server)
        self.assertEqual(dest.gates[0], r.gate)
        self.assertEqual(0, r.cost)

        with self.assertRaises(ValueError):
            r = Route(destination=dest, proxy_server=dest, cost=1)

        ## proxy
        with self.assertRaises(ValueError):
            r = Route(destination=dest, proxy_server=proxy)

        with self.assertRaises(ValueError):
            r = Route(destination=dest, proxy_server=proxy, cost=0)

        r = Route(destination=dest, proxy_server=proxy, cost=1)
        self.assertEqual(dest, r.destination)
        self.assertEqual(proxy, r.proxy_server)
        self.assertIsNone(r.gate)
        self.assertEqual(1, r.cost)

        # route with node with multiple gates
        dest = Server('dest', gates=[('192.168.1.1', 80), ('10.0.0.1', 80)])
        proxy = Server('proxy', gates=[('192.168.1.1', 80), ('10.0.0.1', 80)])
        with patch('dm.domain.entities.route.check_host') as mock_check:
            mock_check.side_effect = [False, True]
            r = Route(destination=dest, proxy_server=dest)
            self.assertEqual(2, mock_check.call_count)
            self.assertEqual(dest, r.destination)
            self.assertIsNone(r.proxy_server)
            self.assertEqual(dest.gates[1], r.gate)
            self.assertEqual(0, r.cost)

            mock_check.side_effect = [False, False]
            with self.assertRaises(ValueError):
                r = Route(destination=dest, proxy_server=dest)

        with patch('dm.domain.entities.route.check_host') as mock_check:
            mock_check.side_effect = [True, False]
            r = Route(destination=dest)
            self.assertEqual(1, mock_check.call_count)
            self.assertEqual(dest, r.destination)
            self.assertIsNone(r.proxy_server)
            self.assertEqual(dest.gates[0], r.gate)
            self.assertEqual(0, r.cost)

            mock_check.side_effect = [False, False]
            with self.assertRaises(ValueError):
                r = Route(destination=dest, proxy_server=dest)

    def test_to_json_proxy_neighbour(self):
        dest = Server('dest', port=8000)

        r = Route(destination=dest, proxy_server=dest)
        with self.assertRaises(RuntimeError):
            r.to_json()

        db.session.add(dest)
        db.session.commit()

        self.assertDictEqual({'destination_id': str(dest.id), 'gate_id': str(dest.gates[0].id),
                              'proxy_server_id': None, 'cost': 0}, r.to_json())

    def test_to_json_proxy_remote(self):
        dest = Server('dest', port=8000)
        proxy = Server('proxy', port=8000)
        r = Route(destination=dest, proxy_server=proxy, cost=1)
        with self.assertRaises(RuntimeError):
            r.to_json()

        db.session.add_all([dest, proxy])
        db.session.commit()

        self.assertDictEqual({'destination_id': str(dest.id), 'gate_id': None,
                              'proxy_server_id': str(proxy.id), 'cost': 1}, r.to_json())