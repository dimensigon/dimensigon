import datetime as dt
import json
import re
from unittest import TestCase
from unittest.mock import patch

import responses
from aioresponses import aioresponses
from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import Gate, Locker, Catalog
from dimensigon.domain.entities import Server, Route, Dimension, User
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils.helpers import generate_dimension
from dimensigon.web import create_app, db
from dimensigon.web.background_tasks import TempRoute, update_table_routing_cost, process_catalog_route_table
from tests.helpers import set_callbacks


class TestUpdateTableRoutingCost(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        User.set_initial()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dimensigon.web.background_tasks.check_host', autospec=True)
    @patch('dimensigon.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario1(self, mocked_ping, mocked_check_host):
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1')
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g2 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id='123e4567-e89b-12d3-a456-426655440003', name='node3', me=True)
        g3 = Gate(id='123e4567-e89b-12d3-a456-426655440013', server=s3, port=5003,
                  dns=s3.name)
        Route(s1, gate=g1, cost=0)
        db.session.add_all([s1, s2, s3])

        def callback(request):

            if request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440001').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440001',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
                                gate_id='123e4567-e89b-12d3-a456-426655440012', proxy_server_id=None, cost=0),
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                gate_id='123e4567-e89b-12d3-a456-426655440013', proxy_server_id=None, cost=0),
                       ]}
            elif request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440002').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440002',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                gate_id='123e4567-e89b-12d3-a456-426655440011', proxy_server_id=None, cost=0),
                       ]}
            else:
                raise
            return 200, {}, json.dumps(msg)

        responses.add_callback(responses.GET, re.compile('^https?://.*$'), callback=callback,
                               content_type='application/json')

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return None, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_check_host.side_effect = check_host

        changed_routes = update_table_routing_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertEqual(g1, s1.route.gate)
        self.assertEqual(None, s1.route.proxy_server)
        self.assertEqual(0, s1.route.cost)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertIsNone(s3.route)
        self.assertDictEqual({s2: (None, g2, 0)}, changed_routes)

    @patch('dimensigon.web.background_tasks.check_host', autospec=True)
    @patch('dimensigon.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario2(self, mocked_ping, mocked_check_host):
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g2 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id='123e4567-e89b-12d3-a456-426655440003', name='node3')
        g3 = Gate(id='123e4567-e89b-12d3-a456-426655440013', server=s3, port=5003,
                  dns=s3.name)
        Route(s2, gate=g2, cost=0)
        Route(s3, gate=g3, cost=0)
        db.session.add_all([s1, s2, s3])

        def callback(request):
            if request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440002').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440002',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                gate_id='123e4567-e89b-12d3-a456-426655440011', proxy_server_id=None, cost=0),
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                gate_id='123e4567-e89b-12d3-a456-426655440013', proxy_server_id=None, cost=0),
                       ]}
            else:
                raise
            return 200, {}, json.dumps(msg)

        responses.add_callback(responses.GET, re.compile('^https?://.*$'), callback=callback,
                               content_type='application/json')

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return None, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False

        mocked_check_host.side_effect = check_host

        changed_routes = update_table_routing_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

        self.assertDictEqual({s3: (s2, None, 1)}, changed_routes)

    @patch('dimensigon.web.background_tasks.check_host', autospec=True)
    @patch('dimensigon.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario3(self, mocked_ping, mocked_check_host):
        # Node 1 loses connection to gate's Node 2 and sets the second gate as default gate
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g21 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5012,
                   dns=s2.name)
        g22 = Gate(id='123e4567-e89b-12d3-a456-426655440022', server=s2, port=5022,
                   dns=s2.name)

        Route(s2, gate=g21, cost=0)
        db.session.add_all([s1, s2])

        def callback(request):
            if request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440002').url('api_1_0.routes').replace(
                    '5012', '5022'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440002',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                gate_id='123e4567-e89b-12d3-a456-426655440011', proxy_server_id=None, cost=0),
                       ]}
            else:
                raise
            return 200, {}, json.dumps(msg)

        responses.add_callback(responses.GET, re.compile('^https?://.*$'), callback=callback,
                               content_type='application/json')

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return None, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1' and port == 5001:
                return True
            elif host == 'node2' and port == 5012:
                return False
            elif host == 'node2' and port == 5022:
                return True
            else:
                return False

        mocked_check_host.side_effect = check_host

        changed_routes = update_table_routing_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g22, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({s2: TempRoute(
            None, g22, 0)}, changed_routes)

    @patch('dimensigon.web.background_tasks.check_host', autospec=True)
    @patch('dimensigon.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario4(self, mocked_ping, mocked_check_host):
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g2 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id='123e4567-e89b-12d3-a456-426655440003', name='node3')
        g3 = Gate(id='123e4567-e89b-12d3-a456-426655440013', server=s3, port=5003,
                  dns=s3.name)
        Route(s2, gate=g2, cost=0)
        Route(s3, gate=g3, cost=0)
        db.session.add_all([s1, s2, s3])

        def callback(request):
            if request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440002').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440002',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                gate_id='123e4567-e89b-12d3-a456-426655440011', proxy_server_id=None, cost=0),
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                gate_id=None, proxy_server_id=None, cost=None),
                       ]}
            else:
                raise
            return 200, {}, json.dumps(msg)

        responses.add_callback(responses.GET, re.compile('^https?://.*$'), callback=callback,
                               content_type='application/json')

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return None, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False

        mocked_check_host.side_effect = check_host

        changed_routes = update_table_routing_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

        self.assertDictEqual({s3: TempRoute(
            None, None, None)}, changed_routes)

    @patch('dimensigon.web.background_tasks.check_host', autospec=True)
    @patch('dimensigon.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario5(self, mocked_ping, mocked_check_host):
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g2 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5012,
                  dns=s2.name)

        Route(s2, gate=g2, cost=0)
        db.session.add_all([s1, s2])

        def callback(request):
            if request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440002').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440002',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                gate_id='123e4567-e89b-12d3-a456-426655440011', proxy_server_id=None, cost=0),
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                gate_id='123e4567-e89b-12d3-a456-426655440013', proxy_server_id=None, cost=0),
                       ]}
            else:
                raise
            return 200, {}, json.dumps(msg)

        responses.add_callback(responses.GET, re.compile('^https?://.*$'), callback=callback,
                               content_type='application/json')

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None

        mocked_ping.side_effect = ping

        mocked_check_host.assert_not_called()

        changed_routes = update_table_routing_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({}, changed_routes)

    @patch('dimensigon.web.background_tasks.check_host', autospec=True)
    @patch('dimensigon.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario6(self, mocked_ping, mocked_check_host):
        # Nodes have localhost and node2 is not a neighbour anymore
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g11 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5000,
                   ip='127.0.0.1')
        g12 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s1, port=5000,
                   ip='10.0.0.1')

        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g21 = Gate(id='123e4567-e89b-12d3-a456-426655440021', server=s2, port=5000,
                   ip='127.0.0.1')
        g22 = Gate(id='123e4567-e89b-12d3-a456-426655440022', server=s2, port=5000,
                   ip='10.0.0.2')

        Route(s2, gate=g22, cost=0)
        db.session.add_all([s1, s2])
        db.session.commit()

        def callback(request):
            if request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440001').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440001',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
                                gate_id='123e4567-e89b-12d3-a456-426655440022', proxy_server_id=None, cost=0),
                       ]}
            else:
                raise
            return 200, {}, json.dumps(msg)

        responses.add(responses.GET, url=Server.query.get('123e4567-e89b-12d3-a456-426655440001').url('api_1_0.routes'),
                      json={"server_id": '123e4567-e89b-12d3-a456-426655440001',
                            "route_list": [
                                dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
                                     gate_id='123e4567-e89b-12d3-a456-426655440022', proxy_server_id=None, cost=0),
                            ]})

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return None, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == '127.0.0.1':
                return True
            elif host == '10.0.0.1':
                return True
            elif host == '10.0.0.2':
                return False
            else:
                raise ConnectionError

        mocked_check_host.side_effect = check_host

        changed_routes = update_table_routing_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(None, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(None, s2.route.cost)

        self.assertDictEqual({s2: TempRoute(
            None, None, None)}, changed_routes)

    @patch('dimensigon.web.background_tasks.check_host', autospec=True)
    @patch('dimensigon.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario6(self, mocked_ping, mocked_check_host):
        # Node have localhost and node2 appears as a new neighbour
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g11 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5000,
                   ip='127.0.0.1')
        g12 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s1, port=5000,
                   ip='10.0.0.1')

        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g21 = Gate(id='123e4567-e89b-12d3-a456-426655440021', server=s2, port=5000,
                   ip='127.0.0.1')
        g22 = Gate(id='123e4567-e89b-12d3-a456-426655440022', server=s2, port=5000,
                   ip='10.0.0.2')

        Route(s2, gate=None, cost=None)
        db.session.add_all([s1, s2])
        db.session.commit()

        def callback(request):
            if re.search("^https?://(10\.0\.0\.1|127\.0\.0\.1):5000" + url_for('api_1_0.routes', _external=False),
                         request.url):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440001',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
                                gate_id='123e4567-e89b-12d3-a456-426655440022', proxy_server_id=None, cost=0),
                       ]}
            elif re.search("^https?://(10\.0\.0\.2):5000" + url_for('api_1_0.routes', _external=False),
                           request.url):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440002',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                gate_id='123e4567-e89b-12d3-a456-426655440012', proxy_server_id=None, cost=0),
                       ]}
            else:
                raise ConnectionError()
            return 200, {}, json.dumps(msg)

        responses.add_callback(responses.GET, re.compile('^https?://.*$'), callback=callback,
                               content_type='application/json')

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return None, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == '127.0.0.1':
                return True
            elif host == '10.0.0.1':
                return True
            elif host == '10.0.0.2':
                return True
            else:
                raise ConnectionError

        mocked_check_host.side_effect = check_host

        changed_routes = update_table_routing_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g22, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({s2: TempRoute(
            None, g22, 0)}, changed_routes)

        db.session.commit()


class TestProcessCatalogRouteTable(TestCase):

    @patch('dimensigon.domain.entities.get_now')
    def setUp(self, mock_now):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app.config['SECURIZER'] = True
        mock_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        with self.app.app_context():
            self.dim = generate_dimension('test')
            self.dim.current = True
            self.json_dim = self.dim.to_json()
            self.client = self.app.test_client()

            db.create_all()
            Locker.set_initial()
            User.set_initial()

            self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))

            server = Server('node1', dns_or_ip='127.0.0.1', port=8000, me=True)
            for g in server.gates:
                g.last_modified_at = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
            db.session.add_all([server, self.dim])
            db.session.commit()

            # dump data
            self.json_node1 = server.to_json(add_gates=True)
            self.json_users = [u.to_json() for u in User.query.all()]

        self.app2 = create_app('test')
        self.app2.config['SECURIZER'] = True
        self.client2 = self.app2.test_client()
        mock_now.return_value = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
        with self.app2.app_context():
            db.create_all()
            Locker.set_initial()
            User.set_initial()

            me = Server('node2', port=8000, me=True, granules='granule',
                        last_modified_at=dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc))
            for g in me.gates:
                g.last_modified_at = dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc)
            db.session.add(me)

            src_server = Server.from_json(self.json_node1)
            Route(src_server, cost=0)
            db.session.add(src_server)

            dim = Dimension.from_json(self.json_dim)
            dim.current = True
            db.session.add(dim)

            users = [User.from_json(ju) for ju in self.json_users]
            db.session.add_all(users)

            db.session.commit()

            # dump data
            self.json_node2 = me.to_json(add_gates=True)

        mock_now.return_value = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
        with self.app.app_context():
            node2 = Server.from_json(self.json_node2)
            node2.last_modified_at = dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc)
            Route(node2, cost=0)
            db.session.add(node2)
            db.session.commit()

    def tearDown(self) -> None:
        with self.app2.app_context():
            db.session.remove()
            db.drop_all()

        with self.app.app_context():
            db.session.remove()
            db.drop_all()


    @responses.activate
    @aioresponses()
    @patch('dimensigon.web.background_tasks.update_table_routing_cost', return_value=True)
    @patch('dimensigon.web.background_tasks.upgrade_version', return_value=False)
    def test_catalog(self, m, mock_version, mock_routing):
        # test all system from process_catalog_route_table to lock server and upgrade catalog
        set_callbacks([("(127.0.0.1|node1)", self.app.test_client()),
                       ("node2", self.app2.test_client())], m=m)

        with self.app.app_context():
            datemark = Catalog.max_catalog()
        self.assertEqual(dt.datetime(2019, 4, 1, tzinfo=dt.timezone.utc), datemark)

        process_catalog_route_table(self.app)

        with self.app.app_context():
            datemark = Catalog.max_catalog()
        self.assertEqual(dt.datetime(2019, 4, 2, tzinfo=dt.timezone.utc), datemark.astimezone(dt.timezone.utc))
