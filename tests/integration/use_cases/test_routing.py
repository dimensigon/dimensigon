import json
import re
from unittest.case import TestCase
from unittest.mock import patch

import responses
from flask import url_for

from dimensigon.domain.entities import User, Server, Gate, Route
from dimensigon.domain.entities.server import RouteContainer
from dimensigon.use_cases.routing import update_route_table_cost, update_route_table_from_data
from dimensigon.web import create_app, db


class TestUpdateRouteTableCost(TestCase):

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

    @patch('dimensigon.use_cases.routing.check_host', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario1(self, mocked_check_host):
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

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_check_host.side_effect = check_host

        changed_routes = update_route_table_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertEqual(g1, s1.route.gate)
        self.assertEqual(None, s1.route.proxy_server)
        self.assertEqual(0, s1.route.cost)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertIsNone(s3.route)
        self.assertDictEqual({s2: (None, g2, 0)}, changed_routes)

    @patch('dimensigon.use_cases.routing.check_host', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario2(self, mocked_check_host):
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

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False

        mocked_check_host.side_effect = check_host

        changed_routes = update_route_table_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

        self.assertDictEqual({s3: (s2, None, 1)}, changed_routes)

    @patch('dimensigon.use_cases.routing.check_host', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario3(self, mocked_check_host):
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

        changed_routes = update_route_table_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g22, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({s2: RouteContainer(
            None, g22, 0)}, changed_routes)

    @patch('dimensigon.use_cases.routing.check_host', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario4(self, mocked_check_host):
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

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False

        mocked_check_host.side_effect = check_host

        changed_routes = update_route_table_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

        self.assertDictEqual({s3: RouteContainer(
            None, None, None)}, changed_routes)

    @patch('dimensigon.use_cases.routing.check_host', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario5(self, mocked_check_host):
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

        mocked_check_host.assert_not_called()

        changed_routes = update_route_table_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({}, changed_routes)

    @patch('dimensigon.use_cases.routing.check_host', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario6(self, mocked_check_host):
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

        changed_routes = update_route_table_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(None, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(None, s2.route.cost)

        self.assertDictEqual({s2: RouteContainer(
            None, None, None)}, changed_routes)

    @patch('dimensigon.use_cases.routing.check_host', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario6(self, mocked_check_host):
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

        changed_routes = update_route_table_cost(discover_new_neighbours=True, check_current_neighbours=True)

        self.assertIsNone(s1.route)

        self.assertEqual(g22, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({s2: RouteContainer(
            None, g22, 0)}, changed_routes)

        db.session.commit()


class TestUpdateRouteTableFromData(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.maxDiff = None
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

    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch(self, mocked_ping):

        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='server1', me=True)
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='server2')
        g2 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5002,
                  dns=s2.name)
        Route(s2, gate=g2, cost=0)

        s3 = Server(id='123e4567-e89b-12d3-a456-426655440003', name='server3')
        g3 = Gate(id='123e4567-e89b-12d3-a456-426655440013', server=s3, port=5003,
                  dns=s3.name)
        Route(s3, gate=g3, cost=0)

        s4 = Server(id='123e4567-e89b-12d3-a456-426655440004', name='server4')
        g4 = Gate(id='123e4567-e89b-12d3-a456-426655440014', server=s4, port=5001,
                  dns=s4.name)
        Route(s4, proxy_server=s2, cost=1)
        db.session.add_all([s1, s2, s3, s4])

        # Server2 loses connectivity to Server4
        mocked_ping.return_value = (None, None)

        new_routes = update_route_table_from_data({"server_id": '123e4567-e89b-12d3-a456-426655440002',
                                                   "route_list": [
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440004',
                                                            gate_id=None,
                                                            proxy_server_id=None,
                                                            cost=None)]})

        self.assertDictEqual({s4: RouteContainer(None, None, None)}, new_routes)

        # s = Server.query.get('123e4567-e89b-12d3-a456-426655440002')
        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        # s = Server.query.get('123e4567-e89b-12d3-a456-426655440003')
        self.assertEqual(g3, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

        # s = Server.query.get('123e4567-e89b-12d3-a456-426655440004')
        self.assertEqual(None, s4.route.gate)
        self.assertEqual(None, s4.route.proxy_server)
        self.assertEqual(None, s4.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch_scenario1(self, mocked_ping, mocked_check_host):
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
        db.session.add_all([s1, s2, s3])
        db.session.commit()

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return 0, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_check_host.side_effect = check_host

        new_routes = update_route_table_from_data({"server_id": '123e4567-e89b-12d3-a456-426655440003',
                                                   "route_list": [
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                                            gate_id='123e4567-e89b-12d3-a456-426655440011',
                                                            proxy_server_id=None,
                                                            cost=0),
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
                                                            gate_id='123e4567-e89b-12d3-a456-426655440012',
                                                            proxy_server_id=None,
                                                            cost=0)
                                                   ]})

        self.assertDictEqual({s3: RouteContainer(None, g3, 0)}, new_routes)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(g3, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch_scenario2(self, mocked_ping, mocked_check_host):
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
        db.session.add_all([s1, s2, s3])
        db.session.commit()

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return None, None
            else:
                raise

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False
            else:
                raise

        mocked_check_host.side_effect = check_host

        new_routes = update_route_table_from_data({"server_id": '123e4567-e89b-12d3-a456-426655440002',
                                                   "route_list": [
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                                            gate_id='123e4567-e89b-12d3-a456-426655440013',
                                                            proxy_server_id=None,
                                                            cost=0),
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
                                                            gate_id='123e4567-e89b-12d3-a456-426655440012',
                                                            proxy_server_id=None,
                                                            cost=0)
                                                   ]})

        self.assertDictEqual({s3: RouteContainer(s2, None, 1)}, new_routes)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch_scenario3(self, mocked_ping, mocked_check_host):
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
        Route(s3, proxy_server=s2, cost=1)
        db.session.add_all([s1, s2, s3])
        db.session.commit()

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return 1, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_check_host.side_effect = check_host

        new_routes = update_route_table_from_data({"server_id": '123e4567-e89b-12d3-a456-426655440003',
                                                   "route_list": [
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                                            gate_id='123e4567-e89b-12d3-a456-426655440011',
                                                            proxy_server_id=None,
                                                            cost=0)
                                                   ]})

        self.assertDictEqual({s3: RouteContainer(None, g3, 0)}, new_routes)
        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(g3, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch_scenario4(self, mocked_ping, mocked_check_host):
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5001,
                  dns=s1.name)
        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g2 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id='123e4567-e89b-12d3-a456-426655440003', name='node3')
        g3 = Gate(id='123e4567-e89b-12d3-a456-426655440013', server=s3, port=5003,
                  dns=s3.name)

        db.session.add_all([s1, s2, s3])
        db.session.commit()

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

        new_routes = update_route_table_from_data({"server_id": '123e4567-e89b-12d3-a456-426655440002',
                                                   "route_list": [
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                                            gate_id='123e4567-e89b-12d3-a456-426655440011',
                                                            proxy_server_id=None,
                                                            cost=0),
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                                            gate_id='123e4567-e89b-12d3-a456-426655440013',
                                                            proxy_server_id=None,
                                                            cost=0)
                                                   ]})
        self.assertDictEqual({s2: RouteContainer(None, g2, 0),
                              s3: RouteContainer(s2, None, 1)}, new_routes)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch_scenario5(self, mocked_ping, mocked_check_host):
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
        db.session.commit()

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return 0, None

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_check_host.side_effect = check_host

        new_routes = update_route_table_from_data({"server_id": '123e4567-e89b-12d3-a456-426655440002',
                                                   "route_list": [
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                                            gate_id=None,
                                                            proxy_server_id=None,
                                                            cost=None)
                                                   ]})

        self.assertDictEqual({}, new_routes)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(g3, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch_scenario6(self, mocked_ping, mocked_check_host):
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
        db.session.commit()

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

        new_routes = update_route_table_from_data({"server_id": s2.id,
                                                   "route_list": [
                                                       dict(destination_id=s3.id,
                                                            gate_id=None,
                                                            proxy_server_id=None,
                                                            cost=None)
                                                   ]})

        self.assertDictEqual({s3: RouteContainer(None, None, None)}, new_routes)

        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch_scenario7(self, mocked_ping, mocked_check_host):
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5001,
                  dns=s1.name)
        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g2 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id='123e4567-e89b-12d3-a456-426655440003', name='node3')
        g3 = Gate(id='123e4567-e89b-12d3-a456-426655440013', server=s3, port=5003,
                  dns=s3.name)

        Route(s2, proxy_server=None, gate=g2, cost=0)
        Route(s3, proxy_server=s2, gate=None, cost=1)
        db.session.add_all([s1, s2, s3])
        db.session.commit()

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

        new_routes = update_route_table_from_data({"server_id": '123e4567-e89b-12d3-a456-426655440002',
                                                   "route_list": [
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                                            gate_id=None,
                                                            proxy_server_id=None,
                                                            cost=None)
                                                   ]})

        self.assertDictEqual({s3: RouteContainer(None, None, None)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test_routes_patch_scenario8(self, mocked_ping, mocked_check_host):
        s1 = Server(id='123e4567-e89b-12d3-a456-426655440001', name='node1', me=True)
        g1 = Gate(id='123e4567-e89b-12d3-a456-426655440011', server=s1, port=5000,
                  dns=s1.name)
        s2 = Server(id='123e4567-e89b-12d3-a456-426655440002', name='node2')
        g2 = Gate(id='123e4567-e89b-12d3-a456-426655440012', server=s2, port=5000,
                  dns=s2.name)
        s3 = Server(id='123e4567-e89b-12d3-a456-426655440003', name='node3')
        g3 = Gate(id='123e4567-e89b-12d3-a456-426655440013', server=s3, port=5000,
                  dns=s3.name)

        s4 = Server(id='123e4567-e89b-12d3-a456-426655440004', name='node4')
        g4 = Gate(id='123e4567-e89b-12d3-a456-426655440014', server=s4, port=5000,
                  dns=s4.name)

        Route(s2, proxy_server=None, gate=g2, cost=0)
        Route(s3, proxy_server=s2, gate=None, cost=1)
        Route(s4, proxy_server=s2, gate=None, cost=1)
        db.session.add_all([s1, s2, s3, s4])
        db.session.commit()

        def ping(server, *args, **kwargs):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return 1, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440004':
                return None, None
            else:
                raise

        mocked_ping.side_effect = ping

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False
            elif host == 'node4':
                return False
            else:
                raise

        mocked_check_host.side_effect = check_host

        new_routes = update_route_table_from_data({"server_id": '123e4567-e89b-12d3-a456-426655440002',
                                                   "route_list": [
                                                       dict(destination_id='123e4567-e89b-12d3-a456-426655440004',
                                                            gate_id=None,
                                                            proxy_server_id=s3.id,
                                                            cost=1),

                                                   ]})

        self.assertDictEqual({s4: RouteContainer(s3, None, 2)}, new_routes)

        self.assertEqual(1, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

        self.assertEqual(None, s4.route.gate)
        self.assertEqual(s3, s4.route.proxy_server)
        self.assertEqual(2, s4.route.cost)