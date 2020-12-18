import re
import threading
from unittest import mock
from unittest.mock import patch

from aioresponses import aioresponses
from flask import url_for

from dimensigon.domain.entities import Server, Gate, Route
from dimensigon.domain.entities.route import RouteContainer
from dimensigon.use_cases.routing import RouteManager
from dimensigon.utils import asyncio
from dimensigon.web import db
from tests.base import TestDimensigonBase


class TestRouteManager(TestDimensigonBase):
    scopefunc = None

    def setUp(self):
        self.maxDiff = None
        super().setUp()

        self.new_event = threading.Event()
        self.mock_queue = mock.Mock()
        self.mock_dm = mock.Mock()
        self.mock_dm.flask_app = self.app
        self.mock_dm.engine = db.engine
        self.mock_dm.manager.dict.return_value = dict()

        self.rm = RouteManager("Manager", startup_event=threading.Event(), shutdown_event=threading.Event(),
                               publish_q=self.mock_queue, event_q=None, dimensigon=self.mock_dm)

        self.rm.session = db.session

        self.mock_dm._server = self.s1 = Server(id='00000000-0000-0000-0000-000000000001', name='node1', me=True)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario1(self, m, mocked_async_check_host):
        g1 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001,
                  dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g2 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g3 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003,
                  dns=s3.name)
        Route(s3, g3, cost=0)
        db.session.add_all([s2, s3])
        db.session.commit()

        m.get(re.compile('https?://node3:5003.*'),
              payload={"server_id": '00000000-0000-0000-0000-000000000003',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000002',
                                gate_id='00000000-0000-0000-0000-000000000012', proxy_server_id=None, cost=0),
                           dict(destination_id='00000000-0000-0000-0000-000000000001',
                                gate_id='00000000-0000-0000-0000-000000000011', proxy_server_id=None, cost=0),
                       ]})
        m.get(re.compile('https?://node2:5002.*'),
              payload={"server_id": '00000000-0000-0000-0000-000000000002',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000003',
                                gate_id='00000000-0000-0000-0000-000000000013', proxy_server_id=None, cost=0),
                       ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_async_check_host.side_effect = async_check_host
        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertDictEqual({s2: RouteContainer(None, g2, 0)}
                             , changed_routes)

        self.assertIsNone(self.s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(g3, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario2(self, m, mocked_async_check_host):
        g1 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001,
                  dns=self.s1.name)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g2 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g3 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003,
                  dns=s3.name)
        Route(s2, g2, cost=0)
        Route(s3, g3, cost=0)
        db.session.add_all([s2, s3])
        db.session.commit()  # commit to check constraint validations

        m.get(re.compile('https?://node2:5002.*'),
              payload={"server_id": '00000000-0000-0000-0000-000000000002',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000001',
                                gate_id='00000000-0000-0000-0000-000000000011', proxy_server_id=None, cost=0),
                           dict(destination_id='00000000-0000-0000-0000-000000000003',
                                gate_id='00000000-0000-0000-0000-000000000013', proxy_server_id=None, cost=0),
                       ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False

        mocked_async_check_host.side_effect = async_check_host

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertIsNone(self.s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

        self.assertDictEqual({s3: RouteContainer(s2, None, 1)}, changed_routes)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario3(self, m, mocked_async_check_host):
        # Node 1 loses connection to gate's Node 2 and sets the second gate as default gate
        g1 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001,
                  dns=self.s1.name)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g21 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5012,
                   dns=s2.name)
        g22 = Gate(id='00000000-0000-0000-0000-000000000022', server=s2, port=5022,
                   dns=s2.name)

        Route(s2, g21, cost=0)
        db.session.add_all([s2])
        db.session.commit()  # commit to check constraint validations

        m.get(Server.query.get('00000000-0000-0000-0000-000000000002').url('api_1_0.routes').replace(
            '5012', '5022'), payload={"server_id": '00000000-0000-0000-0000-000000000002',
                                      "route_list": [
                                          dict(destination_id='00000000-0000-0000-0000-000000000001',
                                               gate_id='00000000-0000-0000-0000-000000000011', proxy_server_id=None,
                                               cost=0),
                                      ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == 'node1' and port == 5001:
                return True
            elif host == 'node2' and port == 5012:
                return False
            elif host == 'node2' and port == 5022:
                return True
            else:
                return False

        mocked_async_check_host.side_effect = async_check_host

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertIsNone(self.s1.route)

        self.assertEqual(g22, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({s2: RouteContainer(
            None, g22, 0)}, changed_routes)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario4(self, m, mocked_async_check_host):
        g1 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001,
                  dns=self.s1.name)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g2 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g3 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003,
                  dns=s3.name)
        Route(s2, g2, cost=0)
        Route(s3, g3, cost=0)
        db.session.add_all([s2, s3])
        db.session.commit()  # commit to check constraint validations

        m.get(re.compile('https?://node2:5002.*'),
              payload={"server_id": '00000000-0000-0000-0000-000000000002',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000001',
                                gate_id='00000000-0000-0000-0000-000000000011', proxy_server_id=None, cost=0),
                           dict(destination_id='00000000-0000-0000-0000-000000000003',
                                gate_id=None, proxy_server_id=None, cost=None),
                       ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False

        mocked_async_check_host.side_effect = async_check_host

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertIsNone(self.s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

        self.assertDictEqual({s3: RouteContainer(
            None, None, None)}, changed_routes)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario5(self, m, mocked_async_check_host):
        g1 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001,
                  dns=self.s1.name)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g2 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5012,
                  dns=s2.name)

        Route(s2, g2, cost=0)
        db.session.add_all([s2])
        db.session.commit()  # commit to check constraint validations

        m.get(re.compile('https?://node2:5002.*'),
              payload={"server_id": '00000000-0000-0000-0000-000000000002',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000001',
                                gate_id='00000000-0000-0000-0000-000000000011', proxy_server_id=None, cost=0),
                           dict(destination_id='00000000-0000-0000-0000-000000000003',
                                gate_id='00000000-0000-0000-0000-000000000013', proxy_server_id=None, cost=0),
                       ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            else:
                raise

        mocked_async_check_host.side_effect = async_check_host

        mocked_async_check_host.assert_not_called()

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertIsNone(self.s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({}, changed_routes)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario6(self, m, mocked_async_check_host):
        # Nodes have localhost and node2 is not a neighbour anymore
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000,
                   ip='127.0.0.1')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=self.s1, port=5000,
                   ip='10.0.0.1')

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g21 = Gate(id='00000000-0000-0000-0000-000000000021', server=s2, port=5000,
                   ip='127.0.0.1')
        g22 = Gate(id='00000000-0000-0000-0000-000000000022', server=s2, port=5000,
                   ip='10.0.0.2')

        Route(s2, g22, cost=0)
        db.session.add_all([s2])
        db.session.commit()  # commit to check constraint validations

        m.get(re.compile('https?://node1:5001.*'),
              payload={"server_id": '00000000-0000-0000-0000-000000000001',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000002',
                                gate_id='00000000-0000-0000-0000-000000000022', proxy_server_id=None, cost=0),
                       ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == '127.0.0.1':
                return True
            elif host == '10.0.0.1':
                return True
            elif host == '10.0.0.2':
                return False
            else:
                raise ConnectionError

        mocked_async_check_host.side_effect = async_check_host

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertIsNone(self.s1.route)

        self.assertEqual(None, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(None, s2.route.cost)

        self.assertDictEqual({s2: RouteContainer(
            None, None, None)}, changed_routes)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario7(self, m, mocked_async_check_host):
        # lose contact with a proxy node
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g21 = Gate(id='00000000-0000-0000-0000-000000000021', server=s2)

        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g31 = Gate(id='00000000-0000-0000-0000-000000000031', server=s3)

        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g41 = Gate(id='00000000-0000-0000-0000-000000000041', server=s4)

        Route(s2, g21, cost=0)
        Route(s3, s2, cost=1)
        Route(s4, s2, cost=2)
        db.session.add_all([s2, s3, s4])
        db.session.commit()  # commit to check constraint validations

        async def async_check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return False
            elif host == 'node3':
                return False
            elif host == 'node4':
                return False
            else:
                raise ConnectionError

        mocked_async_check_host.side_effect = async_check_host

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertIsNone(self.s1.route)

        self.assertEqual(None, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(None, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

        self.assertEqual(None, s4.route.gate)
        self.assertEqual(None, s4.route.proxy_server)
        self.assertEqual(None, s4.route.cost)

        self.assertDictEqual({s2: RouteContainer(None, None, None),
                              s3: RouteContainer(None, None, None),
                              s4: RouteContainer(None, None, None),
                              }, changed_routes)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario8(self, m, mocked_async_check_host):
        # Node returns new nodes
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g21 = Gate(id='00000000-0000-0000-0000-000000000021', server=s2)

        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g31 = Gate(id='00000000-0000-0000-0000-000000000031', server=s3)
        s3.route = None

        Route(s2, g21, cost=0)
        # No route to s3

        db.session.add_all([s2, s3])
        db.session.commit()  # commit to check constraint validations

        m.get(re.compile("^https?://node2:\d+" + url_for('api_1_0.routes', _external=False)),
              payload={"server_id": '00000000-0000-0000-0000-000000000002',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000002',
                                gate_id='00000000-0000-0000-0000-000000000021', proxy_server_id=None, cost=0),
                           dict(destination_id='00000000-0000-0000-0000-000000000003',
                                gate_id='00000000-0000-0000-0000-000000000031', proxy_server_id=None, cost=0),
                           dict(destination_id='00000000-0000-0000-0000-000000000004',
                                gate_id=None, proxy_server_id='00000000-0000-0000-0000-000000000003', cost=1)
                       ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False
            elif host == 'node4':
                return False
            else:
                raise ConnectionError

        mocked_async_check_host.side_effect = async_check_host

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=False, check_current_neighbours=False))

        self.assertIsNone(self.s1.route)

        self.assertEqual(g21, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({s3: RouteContainer(s2, None, 1)}, changed_routes)

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario9(self, m, mocked_async_check_host):
        # Node have localhost and node2 appears as a new neighbour
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000,
                   ip='127.0.0.1')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=self.s1, port=5000,
                   ip='10.0.0.1')

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g21 = Gate(id='00000000-0000-0000-0000-000000000021', server=s2, port=5000,
                   ip='127.0.0.1')
        g22 = Gate(id='00000000-0000-0000-0000-000000000022', server=s2, port=5000,
                   ip='10.0.0.2')

        Route(s2, None, cost=None)
        db.session.add_all([s2])
        db.session.commit()  # commit to check constraint validations

        m.get(re.compile("^https?://(10\.0\.0\.1|127\.0\.0\.1):5000" + url_for('api_1_0.routes', _external=False)),
              payload={"server_id": '00000000-0000-0000-0000-000000000001',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000002',
                                gate_id='00000000-0000-0000-0000-000000000022', proxy_server_id=None, cost=0),
                       ]})

        m.get(re.compile("^https?://(10\.0\.0\.2):5000" + url_for('api_1_0.routes', _external=False)),
              payload={"server_id": '00000000-0000-0000-0000-000000000002',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000001',
                                gate_id='00000000-0000-0000-0000-000000000012', proxy_server_id=None, cost=0),
                       ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == '127.0.0.1':
                return True
            elif host == '10.0.0.1':
                return True
            elif host == '10.0.0.2':
                return True
            else:
                raise ConnectionError

        mocked_async_check_host.side_effect = async_check_host

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertIsNone(self.s1.route)

        self.assertEqual(g22, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertDictEqual({s2: RouteContainer(
            None, g22, 0)}, changed_routes)

        db.session.commit()

    @aioresponses()
    @patch('dimensigon.use_cases.routing.async_check_host', autospec=True)
    def test_update_table_routing_cost_scenario10(self, m, mocked_async_check_host):
        # Node have localhost and node2 appears as a new neighbour
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g21 = Gate(id='00000000-0000-0000-0000-000000000021', server=s2)

        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g31 = Gate(id='00000000-0000-0000-0000-000000000031', server=s3)

        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g41 = Gate(id='00000000-0000-0000-0000-000000000041', server=s4)

        Route(s2, g21, cost=0)
        Route(s3, None, cost=None)
        Route(s4, None, cost=None)
        db.session.add_all([s2, s3, s4])
        db.session.commit()  # commit to check constraint validations

        m.get(re.compile("^https?://node1:\d+" + url_for('api_1_0.routes', _external=False)),
              payload={"server_id": '00000000-0000-0000-0000-000000000001',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000002',
                                gate_id='00000000-0000-0000-0000-000000000022', proxy_server_id=None, cost=0),
                       ]})

        m.get(re.compile("^https?://node2:\d+" + url_for('api_1_0.routes', _external=False)),
              payload={"server_id": '00000000-0000-0000-0000-000000000002',
                       "route_list": [
                           dict(destination_id='00000000-0000-0000-0000-000000000002',
                                gate_id='00000000-0000-0000-0000-000000000021', proxy_server_id=None, cost=0),
                           dict(destination_id='00000000-0000-0000-0000-000000000003',
                                gate_id='00000000-0000-0000-0000-000000000031', proxy_server_id=None, cost=0),
                           dict(destination_id='00000000-0000-0000-0000-000000000004',
                                gate_id=None, proxy_server_id='00000000-0000-0000-0000-000000000003', cost=1)
                       ]})

        async def async_check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False
            elif host == 'node4':
                return False
            else:
                raise ConnectionError

        mocked_async_check_host.side_effect = async_check_host

        changed_routes = asyncio.run(
            self.rm._async_refresh_route_table(discover_new_neighbours=True, check_current_neighbours=True))

        self.assertIsNone(self.s1.route)

        self.assertEqual(g21, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

        self.assertEqual(None, s4.route.gate)
        self.assertEqual(s2, s4.route.proxy_server)
        self.assertEqual(2, s4.route.cost)

        self.assertDictEqual({s3: RouteContainer(s2, None, 1),
                              s4: RouteContainer(s2, None, 2),
                              }, changed_routes)

    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data(self, mocked_ping):
        g1 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001, dns=self.s1.name)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='server2')
        g2 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002, dns=s2.name)
        Route(s2, g2, cost=0)

        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='server3')
        g3 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003, dns=s3.name)
        Route(s3, g3, cost=0)

        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='server4')
        g4 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5001, dns=s4.name)
        Route(s4, s2, cost=1)
        db.session.add_all([s2, s3, s4])
        db.session.commit()  # to validate constraints

        # Server2 loses connectivity to Server4
        mocked_ping.return_value = (None, None)

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000004',
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None)]})

        self.assertDictEqual({s4: RouteContainer(None, None, None)}, new_routes)

        # s = Server.query.get('00000000-0000-0000-0000-000000000002')
        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        # s = Server.query.get('00000000-0000-0000-0000-000000000003')
        self.assertEqual(g3, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

        # s = Server.query.get('00000000-0000-0000-0000-000000000004')
        self.assertEqual(None, s4.route.gate)
        self.assertEqual(None, s4.route.proxy_server)
        self.assertEqual(None, s4.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario01(self, mocked_ping, mocked_check_host):
        g1 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g2 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g3 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003, dns=s3.name)

        Route(s2, g2, cost=0)
        db.session.add_all([s2, s3])
        db.session.commit()

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_check_host.side_effect = check_host

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000003',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000001',
                                                                    gate_id='00000000-0000-0000-0000-000000000011',
                                                                    proxy_server_id=None,
                                                                    cost=0),
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000002',
                                                                    gate_id='00000000-0000-0000-0000-000000000012',
                                                                    proxy_server_id=None,
                                                                    cost=0)
                                                            ]})

        self.assertDictEqual({s3: RouteContainer(None, g3, 0)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g2, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(g3, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario02(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003, dns=s3.name)

        Route(s2, g12, cost=0)
        db.session.add_all([s2, s3])
        db.session.commit()

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000003',
                                                                    gate_id='00000000-0000-0000-0000-000000000013',
                                                                    proxy_server_id=None,
                                                                    cost=0),
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000002',
                                                                    gate_id='00000000-0000-0000-0000-000000000012',
                                                                    proxy_server_id=None,
                                                                    cost=0)
                                                            ]})

        self.assertDictEqual({s3: RouteContainer(s2, None, 1)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario03(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003, dns=s3.name)

        Route(s2, g12, cost=0)
        Route(s3, s2, cost=1)
        db.session.add_all([s2, s3])
        db.session.commit()

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_check_host.side_effect = check_host

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000003',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000001',
                                                                    gate_id='00000000-0000-0000-0000-000000000011',
                                                                    proxy_server_id=None,
                                                                    cost=0)
                                                            ]})

        self.assertDictEqual({s3: RouteContainer(None, g13, 0)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(g13, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario04(self, mocked_ping, mocked_check_host):
        s1 = Server(id='00000000-0000-0000-0000-000000000001', name='node1', me=True)
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003, dns=s3.name)

        db.session.add_all([s2, s3])
        db.session.commit()

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False

        mocked_check_host.side_effect = check_host

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000001',
                                                                    gate_id='00000000-0000-0000-0000-000000000011',
                                                                    proxy_server_id=None,
                                                                    cost=0),
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000003',
                                                                    gate_id='00000000-0000-0000-0000-000000000013',
                                                                    proxy_server_id=None,
                                                                    cost=0)
                                                            ]})
        self.assertDictEqual({s2: RouteContainer(None, g12, 0),
                              s3: RouteContainer(s2, None, 1)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertIsNone(s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario05(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003, dns=s3.name)

        Route(s2, g12, cost=0)
        Route(s3, g13, cost=0)
        db.session.add_all([s2, s3])
        db.session.commit()

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return True

        mocked_check_host.side_effect = check_host

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000003',
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None)
                                                            ]})

        self.assertDictEqual({}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(g13, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario06(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003, dns=s3.name)

        Route(s2, g12, cost=0)
        Route(s3, g13, cost=0)
        db.session.add_all([s2, s3])
        db.session.commit()

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return True
            elif host == 'node3':
                return False

        mocked_check_host.side_effect = check_host

        new_routes = self.rm._update_route_table_from_data({"server_id": s2.id,
                                                            "route_list": [
                                                                dict(destination_id=s3.id,
                                                                     gate_id=None,
                                                                     proxy_server_id=None,
                                                                     cost=None)
                                                            ]})

        self.assertDictEqual({s3: RouteContainer(None, None, None)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario07(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5001, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5002, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5003, dns=s3.name)

        Route(s2, g12, cost=0)
        Route(s3, s2, cost=1)
        db.session.add_all([s2, s3])
        db.session.commit()

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000003',
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None)
                                                            ]})

        self.assertDictEqual({s3: RouteContainer(None, None, None)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario08(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)
        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g14 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5000, dns=s4.name)

        Route(s2, g12, cost=0)
        Route(s3, s2, cost=1)
        Route(s4, s2, cost=1)
        db.session.add_all([s2, s3, s4])
        db.session.commit()

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000004',
                                                                    gate_id=None,
                                                                    proxy_server_id=s3.id,
                                                                    cost=1),

                                                            ]})

        self.assertDictEqual({s4: RouteContainer(s2, None, 2)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

        self.assertEqual(None, s4.route.gate)
        self.assertEqual(s2, s4.route.proxy_server)
        self.assertEqual(2, s4.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario09(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)
        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g14 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5000, dns=s4.name)

        Route(s2, g12, cost=0)
        Route(s3, s2, cost=1)
        Route(s4, s2, cost=2)
        db.session.add_all([s2, s3, s4])
        db.session.commit()

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000004',
                                                                    proxy_server_id=None,
                                                                    gate_id=g14.id,
                                                                    cost=0)
                                                            ]})

        self.assertDictEqual({s4: RouteContainer(s2, None, 1)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

        self.assertEqual(None, s4.route.gate)
        self.assertEqual(s2, s4.route.proxy_server)
        self.assertEqual(1, s4.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario10(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)

        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)

        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)

        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g14 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5000, dns=s4.name)

        s5 = Server(id='00000000-0000-0000-0000-000000000005', name='node5')
        g15 = Gate(id='00000000-0000-0000-0000-000000000015', server=s5, port=5000, dns=s5.name)

        Route(s2, g12)
        Route(s3, g13)
        Route(s4, s3, 1)
        Route(s5, s2, 1)
        db.session.add_all([s2, s3, s4, s5])
        db.session.commit()

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000003',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000005',
                                                                    proxy_server_id=s4.id,
                                                                    gate_id=None,
                                                                    cost=1)
                                                            ]})

        self.assertDictEqual({}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(g13, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

        self.assertEqual(None, s4.route.gate)
        self.assertEqual(s3, s4.route.proxy_server)
        self.assertEqual(1, s4.route.cost)

        self.assertEqual(None, s5.route.gate)
        self.assertEqual(s2, s5.route.proxy_server)
        self.assertEqual(1, s5.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario11(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)
        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g14 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5000, dns=s4.name)

        Route(s2, g12)
        Route(s3, s4, 1)
        Route(s4, g14)
        db.session.add_all([s2, s3, s4])
        db.session.commit()

        def ping(server, *args, **kwargs):
            if str(server.id) == '00000000-0000-0000-0000-000000000001':
                return 0, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000002':
                return 0, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000003':
                return 1, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000004':
                return 0, None
            else:
                raise

        mocked_ping.side_effect = ping

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000003',
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None),

                                                            ]})

        self.assertDictEqual({}, new_routes)

        self.assertEqual(1, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s4, s3.route.proxy_server)
        self.assertEqual(1, s3.route.cost)

        self.assertEqual(g14, s4.route.gate)
        self.assertEqual(None, s4.route.proxy_server)
        self.assertEqual(0, s4.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario12(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000011', server=self.s1, port=5000, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)
        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g14 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5000, dns=s4.name)

        Route(s2, g12)
        Route(s3, s4, 1)
        Route(s4, g14)
        db.session.add_all([s2, s3, s4])
        db.session.commit()

        def ping(server, *args, **kwargs):
            if str(server.id) == '00000000-0000-0000-0000-000000000001':
                return 0, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000002':
                return 0, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000003':
                return None, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000004':
                return 0, None
            else:
                raise

        mocked_ping.side_effect = ping

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000003',
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None),

                                                            ]})

        self.assertDictEqual({s3: RouteContainer(None, None, None)}, new_routes)

        self.assertEqual(1, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

        self.assertEqual(g14, s4.route.gate)
        self.assertEqual(None, s4.route.proxy_server)
        self.assertEqual(0, s4.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario13(self, mocked_ping, mocked_check_host):
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)
        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g14 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5000, dns=s4.name)

        Route(s2, s3, 1)
        Route(s3, g13)
        db.session.add_all([s2, s3, s4])
        db.session.commit()

        def ping(server, *args, **kwargs):
            if str(server.id) == '00000000-0000-0000-0000-000000000001':
                return 0, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000002':
                return 1, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000003':
                return 0, None
            elif str(server.id) == '00000000-0000-0000-0000-000000000004':
                return None, None
            else:
                raise

        mocked_ping.side_effect = ping

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000004',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000002',
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None),

                                                            ]})

        self.assertDictEqual({}, new_routes)

        self.assertEqual(1, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(None, s2.route.gate)
        self.assertEqual(s3, s2.route.proxy_server)
        self.assertEqual(1, s2.route.cost)

        self.assertEqual(g13, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(0, s3.route.cost)

        self.assertEqual(None, s4.route.gate)
        self.assertEqual(None, s4.route.proxy_server)
        self.assertEqual(None, s4.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario14(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000012', server=self.s1, port=5000, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)

        Route(s2, g12, 0)
        Route(s3, s2, 1)
        db.session.add_all([s2, s3])
        db.session.commit()

        def check_host(host, port, *args, **kwargs):
            if host == 'node1':
                return True
            elif host == 'node2':
                return False
            elif host == 'node3':
                return False
            elif host == 'node4':
                return False
            else:
                raise

        mocked_check_host.side_effect = check_host

        new_routes = self.rm._update_route_table_from_data({"server_id": s3.id,
                                                            "route_list": [
                                                                dict(
                                                                    destination_id=self.s1.id,
                                                                    gate_id=g11.id,
                                                                    proxy_server_id=None,
                                                                    cost=0),
                                                                dict(
                                                                    destination_id=s2.id,
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None),
                                                            ]})

        self.assertDictEqual({s2: RouteContainer(None, None, None),
                              s3: RouteContainer(None, None, None)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertEqual(2, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(None, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(None, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario15(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000012', server=self.s1, port=5000, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)

        Route(s2, g12, 0)
        Route(s3, s2, 1)
        db.session.add_all([s2, s3])
        db.session.commit()

        new_routes = self.rm._update_route_table_from_data({"server_id": s2.id,
                                                            "route_list": [
                                                                dict(
                                                                    destination_id=s3.id,
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None),
                                                            ]})

        self.assertDictEqual({s3: RouteContainer(None, None, None)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(None, s3.route.proxy_server)
        self.assertEqual(None, s3.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_scenario16(self, mocked_ping, mocked_check_host):
        g11 = Gate(id='00000000-0000-0000-0000-000000000012', server=self.s1, port=5000, dns=self.s1.name)
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)
        s3 = Server(id='00000000-0000-0000-0000-000000000003', name='node3')
        g13 = Gate(id='00000000-0000-0000-0000-000000000013', server=s3, port=5000, dns=s3.name)
        s4 = Server(id='00000000-0000-0000-0000-000000000004', name='node4')
        g14 = Gate(id='00000000-0000-0000-0000-000000000014', server=s4, port=5000, dns=s4.name)
        s5 = Server(id='00000000-0000-0000-0000-000000000005', name='node5')
        g15 = Gate(id='00000000-0000-0000-0000-000000000015', server=s5, port=5000, dns=s5.name)

        Route(s2, g12, 0)
        Route(s3, s2, 3)
        Route(s4, s2, 5)

        db.session.add_all([s2, s3, s4])
        db.session.commit()

        new_routes = self.rm._update_route_table_from_data({"server_id": s3.id,
                                                            "route_list": [
                                                                dict(
                                                                    destination_id=s4.id,
                                                                    gate_id=None,
                                                                    proxy_server_id=s3,
                                                                    cost=1),
                                                            ]})

        self.assertDictEqual({s4: RouteContainer(s3, None, 2)}, new_routes)

        self.assertEqual(0, mocked_ping.call_count)
        self.assertEqual(0, mocked_check_host.call_count)
        self.assertIsNone(self.s1.route)

        self.assertEqual(g12, s2.route.gate)
        self.assertEqual(None, s2.route.proxy_server)
        self.assertEqual(0, s2.route.cost)

        self.assertEqual(None, s3.route.gate)
        self.assertEqual(s2, s3.route.proxy_server)
        self.assertEqual(3, s3.route.cost)

        self.assertEqual(None, s4.route.gate)
        self.assertEqual(s3, s4.route.proxy_server)
        self.assertEqual(2, s4.route.cost)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_unknown_server(self, mocked_ping, mocked_check_host):

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000004',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000002',
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None),

                                                            ]})

        self.assertDictEqual({}, new_routes)

    @patch('dimensigon.use_cases.routing.check_host')
    @patch('dimensigon.use_cases.routing.ntwrk.ping')
    def test__update_route_table_from_data_unknown_destination(self, mocked_ping, mocked_check_host):
        s2 = Server(id='00000000-0000-0000-0000-000000000002', name='node2')
        g12 = Gate(id='00000000-0000-0000-0000-000000000012', server=s2, port=5000, dns=s2.name)

        Route(s2, g12, 0)
        db.session.add_all([s2])

        new_routes = self.rm._update_route_table_from_data({"server_id": '00000000-0000-0000-0000-000000000002',
                                                            "route_list": [
                                                                dict(
                                                                    destination_id='00000000-0000-0000-0000-000000000003',
                                                                    gate_id=None,
                                                                    proxy_server_id=None,
                                                                    cost=None),

                                                            ]})

        self.assertDictEqual({}, new_routes)
