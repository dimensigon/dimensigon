import json
import os
import re
import uuid
from unittest import TestCase, mock
from unittest.mock import patch

import requests
import responses
from flask import url_for
from pkg_resources import parse_version

from dm.domain.entities import Server, Route, Gate, \
    Dimension
from dm.web import create_app, db
from dm.web.background_tasks import TempRoute, update_table_routing_cost, process_get_new_version_from_gogs, \
    upgrader_logger

gogs_content = """
<div class="ui container">
		<h2 class="ui header">
			Releases
		</h2>
		<ul id="release-list">
				<li class="ui grid">
					<div class="ui four wide column meta">
						<span class="commit">
							<a href="/dimensigon/dimensigon/src/d3aad4973fe692c4fcefede8eb53a1c9e32749b2" rel="nofollow"><i class="code icon"></i> d3aad4973f</a>
						</span>
					</div>
					<div class="ui twelve wide column detail">
							<h4>
								<a href="/dimensigon/dimensigon/src/v0.1.a1" rel="nofollow"><i class="tag icon"></i> v0.1.a1</a>
							</h4>
							<div class="download">
								<a href="/dimensigon/dimensigon/archive/v0.1.a1.zip" rel="nofollow"><i class="octicon octicon-file-zip"></i>ZIP</a>
								<a href="/dimensigon/dimensigon/archive/v0.1.a1.tar.gz"><i class="octicon octicon-file-zip"></i>TAR.GZ</a>
							</div>
						<span class="dot">&nbsp;</span>
					</div>
				</li>
				<li class="ui grid">
					<div class="ui four wide column meta">
						<span class="commit">
							<a href="/dimensigon/dimensigon/src/2184389034cec9620c44594ae6c174e676434db5" rel="nofollow"><i class="code icon"></i> 2184389034</a>
						</span>
					</div>
					<div class="ui twelve wide column detail">
							<h4>
								<a href="/dimensigon/dimensigon/src/v0.0.1" rel="nofollow"><i class="tag icon"></i> v0.0.1</a>
							</h4>
							<div class="download">
								<a href="/dimensigon/dimensigon/archive/v0.0.1.zip" rel="nofollow"><i class="octicon octicon-file-zip"></i>ZIP</a>
								<a href="/dimensigon/dimensigon/archive/v0.0.1.tar.gz"><i class="octicon octicon-file-zip"></i>TAR.GZ</a>
							</div>
						<span class="dot">&nbsp;</span>
					</div>
				</li>
		</ul>
		<div class="center">
			<a class="ui small button disabled">
				Página Anterior
			</a>
			<a class="ui small button disabled">
				Página Siguiente
			</a>
		</div>
	</div>
"""


class TestCheckNewVersions(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        Server.set_initial()
        d = Dimension(name='test', current=True)
        db.session.add(d)
        db.session.commit()
        self.client = self.app.test_client(use_cookies=True)

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.web.background_tasks.run_elevator')
    @patch('dm.web.background_tasks.os.path.exists')
    @patch('dm.web.background_tasks.open')
    @responses.activate
    def test_internet_upgrade(self, mock_open, mock_exists, mock_run_elevator):
        with mock.patch('dm.web.background_tasks.dm_version', '0.0.1'):
            responses.add(method='GET',
                          url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000'
                              '/dimensigon/dimensigon/releases',
                          body=gogs_content)

            responses.add(method='GET',
                          url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000'
                              '/dimensigon/dimensigon/archive/v0.1.a1.tar.gz',
                          body=b"v0.1.a1")

            responses.add(method='GET',
                          url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000'
                              '/dimensigon/dimensigon/archive/v0.0.1.tar.gz',
                          body=b"v0.0.1")

            mock_exists.return_value = False
            process_get_new_version_from_gogs(self.app)

            self.assertEqual(
                (os.path.join(self.app.config['SOFTWARE_REPO'], 'dimensigon', 'dimensigon-v0.1.a1.tar.gz'),
                 parse_version('v0.1.a1'),
                 upgrader_logger),
                mock_run_elevator.call_args[0])

    @patch('dm.web.background_tasks.run_elevator')
    @patch('dm.web.background_tasks.os.path.exists')
    @patch('dm.web.background_tasks.open')
    @responses.activate
    def test_internet_not_upgrade(self, mock_open, mock_exists, mock_run_elevator):
        with mock.patch('dm.web.background_tasks.dm_version', '0.1'):
            responses.add(method='GET',
                          url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                          body=gogs_content)

            responses.add(method='GET',
                          url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/archive/v0.1.a1.tar.gz',
                          body=b"v0.1.a1")

            responses.add(method='GET',
                          url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/archive/v0.0.1.tar.gz',
                          body=b"v0.0.1")

            mock_exists.return_value = False
            process_get_new_version_from_gogs()

            self.assertFalse(mock_run_elevator.called)

    @patch('dm.web.background_tasks.run_elevator')
    @patch('dm.web.background_tasks.os.path.exists')
    @patch('dm.web.background_tasks.open')
    @responses.activate
    def test_no_internet_no_upgrade(self, mock_open, mock_exists, mock_run_elevator):
        with mock.patch('dm.web.background_tasks.dm_version', '0.1'):
            responses.add(method='GET',
                          url='https://ca355c55-0ab0-4882-93fa-331bcc4d45bd.pub.cloud.scaleway.com:3000/dimensigon/dimensigon/releases',
                          body=requests.exceptions.ConnectionError('No connection'))

            mock_exists.return_value = False
            process_get_new_version_from_gogs()

            self.assertFalse(mock_run_elevator.called)


# class TestCheckCatalog(TestCase):
#
#     def setUp(self):
#         """Create and configure a new app instance for each test."""
#         # create the app with common test config
#         self.app = create_app('test')
#         self.app_context = self.app.app_context()
#         self.app_context.push()
#         db.create_all()
#         set_initial()
#         self.client = self.app.test_client()
#
#     def tearDown(self) -> None:
#         db.session.remove()
#         db.drop_all()
#         self.app_context.pop()
#
#     @patch('dm.use_cases.interactor.lock_scope')
#     @patch('dm.domain.entities.get_now')
#     @patch('dm.web.background_tasks.upgrade_catalog_from_server')
#     @aioresponses()
#     def test_check_catalog(self, mock_upgrade, mock_now, mock_lock, m):
#         mock_lock.__enter__.return_value = None
#         mock_now.return_value = datetime(2019, 4, 1)
#         s1 = Server('node1', port=8000)
#         Route(destination=s1, cost=0)
#         s2 = Server('node2', port=8000)
#         Route(destination=s2, cost=0)
#         db.session.add_all([s1, s2])
#         db.session.commit()
#
#         m.get(url=s1.url('root.healthcheck'),
#               payload=dict(version=dm.__version__, catalog_version='20190401.000000.000000'))
#         m.get(url=s2.url('root.healthcheck'),
#               payload=dict(version=dm.__version__, catalog_version='20190401.000000.000001'))
#
#         upgrade_catalog()
#
#         mock_upgrade.assert_called_once_with(s2)
#
#     @patch('dm.use_cases.interactor.lock_scope')
#     @patch('dm.domain.entities.get_now')
#     @patch('dm.web.background_tasks.upgrade_catalog_from_server')
#     @aioresponses()
#     def test_check_catalog_no_upgrade(self, mock_upgrade, mock_now, mock_lock, m):
#         mock_lock.__enter__.return_value = None
#         mock_now.return_value = datetime(2019, 4, 1)
#         s1 = Server('node1', port=8000)
#         Route(destination=s1, cost=0)
#         s2 = Server('node2', port=8000)
#         Route(destination=s2, cost=0)
#         db.session.add_all([s1, s2])
#         db.session.commit()
#
#         m.get(url=s1.url('root.healthcheck'),
#               payload=dict(version=dm.__version__, catalog_version='20190401.000000.000000'))
#         m.get(url=s2.url('root.healthcheck'),
#               payload=dict(version=dm.__version__, catalog_version='20190401.000000.000000'))
#
#         upgrade_catalog()
#
#         self.assertEqual(0, mock_upgrade.call_count)
#
#         m.get(url=s1.url('root.healthcheck'), exception=aiohttp.ClientError())
#         m.get(url=s2.url('root.healthcheck'), exception=aiohttp.ClientError())
#
#         check_catalog()
#
#         self.assertEqual(0, mock_upgrade.call_count)


class TestUpdateTableRoutingCost(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('dm.web.background_tasks.check_host', autospec=True)
    @patch('dm.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario1(self, mocked_ping, mocked_check_host):
        s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1')
        g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
        g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3', me=True)
        g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
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

    @patch('dm.web.background_tasks.check_host', autospec=True)
    @patch('dm.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario2(self, mocked_ping, mocked_check_host):
        s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
        g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
        g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
        g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
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

    @patch('dm.web.background_tasks.check_host', autospec=True)
    @patch('dm.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario3(self, mocked_ping, mocked_check_host):
        # Node 1 loses connection to gate's Node 2 and sets the second gate as default gate
        s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
        g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
        g21 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5012,
                   dns=s2.name)
        g22 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440022'), server=s2, port=5022,
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

    @patch('dm.web.background_tasks.check_host', autospec=True)
    @patch('dm.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario4(self, mocked_ping, mocked_check_host):
        s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
        g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
        g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
                  dns=s2.name)
        s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
        g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
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

    @patch('dm.web.background_tasks.check_host', autospec=True)
    @patch('dm.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario5(self, mocked_ping, mocked_check_host):
        s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
        g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
                  dns=s1.name)

        s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
        g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5012,
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

    @patch('dm.web.background_tasks.check_host', autospec=True)
    @patch('dm.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario6(self, mocked_ping, mocked_check_host):
        # Nodes have localhost and node2 is not a neighbour anymore
        s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
        g11 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5000,
                   ip='127.0.0.1')
        g12 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s1, port=5000,
                   ip='10.0.0.1')

        s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
        g21 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440021'), server=s2, port=5000,
                   ip='127.0.0.1')
        g22 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440022'), server=s2, port=5000,
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

    @patch('dm.web.background_tasks.check_host', autospec=True)
    @patch('dm.web.background_tasks.ping', autospec=True)
    @responses.activate
    def test_update_table_routing_cost_scenario6(self, mocked_ping, mocked_check_host):
        # Node have localhost and node2 appears as a new neighbour
        s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
        g11 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5000,
                   ip='127.0.0.1')
        g12 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s1, port=5000,
                   ip='10.0.0.1')

        s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
        g21 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440021'), server=s2, port=5000,
                   ip='127.0.0.1')
        g22 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440022'), server=s2, port=5000,
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
