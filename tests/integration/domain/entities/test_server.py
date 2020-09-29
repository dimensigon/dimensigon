from unittest import TestCase
from unittest.mock import patch

from dimensigon.domain.entities import Server, Route
from dimensigon.web import create_app, db, errors


class TestServer(TestCase):
    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        # set_initial()
        db.create_all()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

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

    @patch('dimensigon.domain.entities.route.check_host')
    @patch('dimensigon.domain.entities.server.url_for')
    def test_url(self, mock_url, mock_check_host):
        self.set_servers_and_routes()

        mock_check_host.return_value = True
        self.assertEqual('http://1.1.1.1:8000', self.n1.url())
        self.assertEqual('http://n2_dns:8000', self.n2.url())
        self.assertEqual('http://n3:8000', self.n3.url())
        self.assertEqual('http://1.1.1.1:8000', self.r1.url())
        self.assertEqual('http://n2_dns:8000', self.r2.url())

        mock_url.return_value = '/'

        self.assertEqual('http://1.1.1.1:8000/', self.n1.url('api'))

        mock_url.assert_called_once_with('api')

        me = Server(name='me', gates=[('127.0.0.1', 5), ('192.168.1.2', 2)], me=True)
        self.assertEqual(f'http://127.0.0.1:5/', me.url('api'))

        self.app.config['PREFERRED_URL_SCHEME'] = 'https'
        me = Server(name='me', gates=[('192.168.1.2', 2)], me=True)
        self.assertEqual(f'https://192.168.1.2:2/', me.url('api'))

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

        self.app.cluster.set_alive(n1.id)

        self.assertListEqual([n1], me.get_neighbours(alive=True))

        self.assertListEqual([n2], me.get_neighbours(exclude=n1))
        self.assertListEqual([n2], me.get_neighbours(exclude=[n1, n3]))

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

    @patch('dimensigon.domain.entities.base.uuid.uuid4')
    def test_from_to_json_with_gate(self, mock_uuid):
        mock_uuid.return_value = '22cd859d-ee91-4079-a112-000000000002'
        s = Server('server2', gates=[('dns', 6000)], id='22cd859d-ee91-4079-a112-000000000001')
        self.assertDictEqual(
            {'id': '22cd859d-ee91-4079-a112-000000000001', 'name': 'server2', 'granules': [],
             'gates': [{'id': '22cd859d-ee91-4079-a112-000000000002', 'ip': None, 'dns': 'dns', 'port': 6000,
                        'hidden': False}]},
            s.to_json(
                add_gates=True))
        db.session.add(s)
        db.session.commit()

        s_json = s.to_json(add_gates=True)
        smashed = Server.from_json(s_json)

        self.assertIs(s, smashed)
        self.assertEqual(s.id, smashed.id)
        self.assertEqual(s.name, smashed.name)
        self.assertEqual(s.granules, smashed.granules)
        self.assertEqual(s.last_modified_at, smashed.last_modified_at)
        self.assertListEqual(s.gates, smashed.gates)

        # from new Server
        db.session.remove()
        db.drop_all()
        db.create_all()

        smashed = Server.from_json(s_json)

        self.assertEqual(s.id, smashed.id)
        self.assertEqual(s.name, smashed.name)
        self.assertEqual(s.granules, smashed.granules)
        self.assertEqual(s.last_modified_at, smashed.last_modified_at)
        self.assertEqual(1, len(smashed.gates))
        self.assertEqual(s.gates[0].id, smashed.gates[0].id)
        self.assertEqual(s.gates[0].ip, smashed.gates[0].ip)
        self.assertEqual(s.gates[0].dns, smashed.gates[0].dns)
        self.assertEqual(s.gates[0].port, smashed.gates[0].port)
