from unittest import TestCase, mock

from dimensigon import defaults
from dimensigon.domain.entities import Server, Route
from dimensigon.utils.helpers import get_now
from dimensigon.web import db, errors
from tests.base import OneNodeMixin


class TestServer(OneNodeMixin, TestCase):

    def set_servers_and_routes(self):
        self.n1 = Server(name='n1', dns_or_ip='1.1.1.1')
        self.n2 = Server(name='n2', dns_or_ip='n2_dns')
        self.n3 = Server(name='n3', port=8000)
        self.r1 = Server(name='r1', dns_or_ip='3.3.3.3')
        self.r2 = Server(name='r2', dns_or_ip='r2_dns')
        db.session.add_all([self.n1, self.n2, self.r1, self.r2])
        db.session.commit()

        Route(destination=self.n1, cost=0)
        Route(destination=self.n2, cost=0)
        Route(destination=self.n3, cost=0)
        Route(destination=self.r1, proxy_server_or_gate=self.n1, cost=1)
        Route(destination=self.r2, proxy_server_or_gate=self.n2, cost=1)

        db.session.commit()

    @mock.patch('dimensigon.domain.entities.route.check_host')
    @mock.patch('dimensigon.domain.entities.server.url_for')
    def test_url(self, mock_url, mock_check_host):
        self.set_servers_and_routes()

        mock_check_host.return_value = True
        self.assertEqual(f'https://1.1.1.1:{defaults.DEFAULT_PORT}', self.n1.url())
        self.assertEqual(f'https://n2_dns:{defaults.DEFAULT_PORT}', self.n2.url())
        self.assertEqual(f'https://n3:8000', self.n3.url())
        self.assertEqual(f'https://1.1.1.1:{defaults.DEFAULT_PORT}', self.r1.url())
        self.assertEqual(f'https://n2_dns:{defaults.DEFAULT_PORT}', self.r2.url())

        mock_url.return_value = '/'

        self.assertEqual(f'https://1.1.1.1:{defaults.DEFAULT_PORT}/', self.n1.url('api'))

        mock_url.assert_called_once_with('api')

        me = Server(name='me', gates=[('127.0.0.1', 5), ('192.168.1.2', 2)], me=True)
        self.assertEqual(f'https://127.0.0.1:5/', me.url('api'))

        with mock.patch('dimensigon.domain.entities.server.current_app') as mock_current_app:
            type(mock_current_app.dm.config).http_config = mock.PropertyMock(return_value={'keyfile': 'x'})
            me = Server(name='me', gates=[('192.168.1.2', 2)], me=True)
            self.assertEqual(f'http://192.168.1.2:2/', me.url('api'))

        s = Server('test', port=8000)
        with self.assertRaises(errors.UnreachableDestination):
            s.url()

    def test_get_neighbours(self):
        n1 = Server('n1', port=8000)
        n2 = Server('n2', port=8000)
        n3 = Server('n3', port=8000)
        r1 = Server('r1', port=8000)
        Route(destination=n1, cost=0)
        Route(destination=n2, proxy_server_or_gate=n2.gates[0])
        Route(destination=r1, proxy_server_or_gate=n1, cost=1)

        me = Server('me', port=8000, me=True)
        db.session.add_all([n1, n2, n3, r1, me])

        self.assertListEqual([n1, n2], me.get_neighbours())

        self.assertListEqual([n2], me.get_neighbours(exclude=n1))
        self.assertListEqual([n2], me.get_neighbours(exclude=[n1, n3]))
        self.assertListEqual([n2], me.get_neighbours(exclude=[n1.id, n3.id]))

    def test_get_neighbours_no_route(self):
        n1 = Server('n1', port=8000)
        me = Server('me', port=8000, me=True)

        db.session.add_all([n1, me])

        self.assertListEqual([], me.get_neighbours())

    def test_get_not_neighbours(self):
        n1 = Server('n1', port=8000, id='22cd859d-ee91-4079-a112-000000000001')
        n2 = Server('n2', port=8000, id='22cd859d-ee91-4079-a112-000000000002')
        n3 = Server('n3', port=8000, id='22cd859d-ee91-4079-a112-000000000003')
        n3.route = None
        r1 = Server('r1', port=8000, id='22cd859d-ee91-4079-a112-000000000011')
        Route(destination=n1, cost=0)
        Route(destination=n2, proxy_server_or_gate=n2.gates[0])
        Route(destination=r1, proxy_server_or_gate=n1, cost=1)

        me = Server('me', port=8000, me=True)
        db.session.add_all([n1, n2, n3, r1, me])

        self.assertListEqual([n3, r1], me.get_not_neighbours())

    def test_get_reachable_servers(self):
        n1 = Server('n1', port=8000, id='22cd859d-ee91-4079-a112-000000000001')
        n2 = Server('n2', port=8000, id='22cd859d-ee91-4079-a112-000000000002')
        n3 = Server('n3', port=8000, id='22cd859d-ee91-4079-a112-000000000003')
        n3.route = None
        n4 = Server('n4', port=8000, id='22cd859d-ee91-4079-a112-000000000004')
        r1 = Server('r1', port=8000, id='22cd859d-ee91-4079-a112-000000000011')
        Route(destination=n1, cost=0)
        Route(destination=n2, proxy_server_or_gate=n2.gates[0])
        Route(destination=n4)
        Route(destination=r1, proxy_server_or_gate=n1, cost=1)

        me = Server('me', port=8000, me=True)
        db.session.add_all([n1, n2, n3, n4, r1, me])

        self.assertListEqual([n1, n2, r1], me.get_reachable_servers())

        self.assertListEqual([n2, r1], me.get_reachable_servers(exclude=n1))
        self.assertListEqual([n2, r1], me.get_reachable_servers(exclude=n1.id))

        self.assertListEqual([r1], me.get_reachable_servers(exclude=[n1.id, n2]))

