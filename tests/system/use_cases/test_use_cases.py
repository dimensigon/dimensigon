import uuid
from unittest import TestCase

from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server, Gate, User
from dm.domain.entities.route import Route
from dm.web import create_app, db
from dm.web.network import HTTPBearerAuth


class TestRoutes(TestCase):

    def setUp(self) -> None:
        self.maxDiff = None
        self.app = create_app('test')
        self.app.config['SECURIZER'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        User.set_initial()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))



    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_routes_get(self):
        s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='server1', me=True)
        g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
                  dns=s1.name)
        s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='server2')
        g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
                  dns=s2.name)
        Route(s2, gate=g2, cost=0)
        s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='server3')
        g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
                  dns=s3.name)
        Route(s3, gate=g3, cost=0)
        s4 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440004'), name='server4')
        g4 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440014'), server=s4, port=5001,
                  dns=s4.name)
        Route(s4, proxy_server=s2, cost=1)
        db.session.add_all([s1, s2, s3, s4])

        response = self.client.get(url_for('api_1_0.routes', _external=False),
                                   headers=self.auth.header)
        data = response.get_json()
        self.assertDictEqual({'server_id': '123e4567-e89b-12d3-a456-426655440001',
                              'route_list': [
                                  dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
                                       gate_id='123e4567-e89b-12d3-a456-426655440012',
                                       proxy_server_id=None, cost=0),
                                  dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                       gate_id='123e4567-e89b-12d3-a456-426655440013',
                                       proxy_server_id=None, cost=0),
                                  dict(destination_id='123e4567-e89b-12d3-a456-426655440004',
                                       gate_id=None,
                                       proxy_server_id='123e4567-e89b-12d3-a456-426655440002', cost=1)]}, data)

    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch(self, mocked_ping, mocked_thread):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='server1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='server2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
    #               dns=s2.name)
    #     Route(s2, gate=g2, cost=0)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='server3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
    #               dns=s3.name)
    #     Route(s3, gate=g3, cost=0)
    #     s4 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440004'), name='server4')
    #     g4 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440014'), server=s4, port=5001,
    #               dns=s4.name)
    #     Route(s4, proxy_server=s2, cost=1)
    #     db.session.add_all([s1, s2, s3, s4])
    #
    #     mocked_ping.return_value = (None, None)
    #     access_token = create_access_token(identity='test')
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers={"Authorization": f"Bearer {access_token}"},
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440004',
    #                                                 gate_id=None,
    #                                                 proxy_server_id=None,
    #                                                 cost=None)]})
    #
    #     # s = Server.query.get('123e4567-e89b-12d3-a456-426655440001')
    #     # self.assertEqual(None, s.route.gate)
    #     # self.assertEqual(None, s.route.proxy_server)
    #     # self.assertEqual(None, s.route.cost)
    #
    #     # s = Server.query.get('123e4567-e89b-12d3-a456-426655440002')
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     # s = Server.query.get('123e4567-e89b-12d3-a456-426655440003')
    #     self.assertEqual(g3, s3.route.gate)
    #     self.assertEqual(None, s3.route.proxy_server)
    #     self.assertEqual(0, s3.route.cost)
    #
    #     # s = Server.query.get('123e4567-e89b-12d3-a456-426655440004')
    #     self.assertEqual(None, s4.route.gate)
    #     self.assertEqual(None, s4.route.proxy_server)
    #     self.assertEqual(None, s4.route.cost)
    #
    #     self.assertEqual(1, mocked_thread.Thread.call_count)
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.update_table_routing_cost')
    # @responses.activate
    # def test_routes_post(self, mocked_utr, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='server1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='server2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5001,
    #               dns=s2.name)
    #     Route(destination=s2, cost=0)
    #     db.session.add_all([s1, s2])
    #
    #     mocked_utr.return_value = {s1: TempRoute(proxy_server=s1, gate=g1, cost=0)}
    #
    #     resp = self.client.post(url_for('api_1_0.routes'),
    #                             json={'discover_new_neighbours': True, 'check_current_neighbours': True},
    #                             headers=self.headers)
    #
    #     mocked_utr.assert_called_once_with(discover_new_neighbours=True, check_current_neighbours=True)
    #
    #     args, kwargs = mocked_threading.Thread.call_args
    #
    #     self.assertTupleEqual((self.app, s2, 'api_1_0.routes'), kwargs['args'])
    #
    #     self.assertDictEqual({'server_id': '123e4567-e89b-12d3-a456-426655440001',
    #                           'route_list': [{'destination_id': '123e4567-e89b-12d3-a456-426655440001',
    #                                           'proxy_server_id': '123e4567-e89b-12d3-a456-426655440001',
    #                                           'gate_id': '123e4567-e89b-12d3-a456-426655440011',
    #                                           'cost': 0}]}, kwargs['kwargs']['json'])
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.check_host')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch_scenario1(self, mocked_ping, mocked_check_host, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
    #               dns=s2.name)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
    #               dns=s3.name)
    #
    #     Route(s2, gate=g2, cost=0)
    #     db.session.add_all([s1, s2, s3])
    #     db.session.commit()
    #
    #     def ping(server, *args, **kwargs):
    #         if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
    #             return 0, None
    #
    #     mocked_ping.side_effect = ping
    #
    #     def check_host(host, port, *args, **kwargs):
    #         if host == 'node1':
    #             return True
    #         elif host == 'node2':
    #             return True
    #         elif host == 'node3':
    #             return True
    #
    #     mocked_check_host.side_effect = check_host
    #
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers=self.headers,
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440003',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
    #                                                 gate_id='123e4567-e89b-12d3-a456-426655440011',
    #                                                 proxy_server_id=None,
    #                                                 cost=0),
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
    #                                                 gate_id='123e4567-e89b-12d3-a456-426655440012',
    #                                                 proxy_server_id=None,
    #                                                 cost=0)
    #                                        ]})
    #
    #     self.assertIsNone(s1.route)
    #
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     self.assertEqual(g3, s3.route.gate)
    #     self.assertEqual(None, s3.route.proxy_server)
    #     self.assertEqual(0, s3.route.cost)
    #
    #     mocked_threading.Thread.assert_called_once()
    #     args, kwargs = mocked_threading.Thread.call_args
    #     kwargs.pop('target')
    #     self.assertDictEqual(dict(args=(self.app, s2, 'api_1_0.routes'),
    #                               kwargs={'json': {'server_id': str(s1.id),
    #                                                'route_list': [
    #                                                    {'destination_id': str(s3.id),
    #                                                     'proxy_server_id': None,
    #                                                     'gate_id': str(g3.id),
    #                                                     'cost': 0}]},
    #                                       'headers': self.headers}), kwargs)
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.check_host')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch_scenario2(self, mocked_ping, mocked_check_host, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
    #               dns=s2.name)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
    #               dns=s3.name)
    #
    #     Route(s2, gate=g2, cost=0)
    #     db.session.add_all([s1, s2, s3])
    #     db.session.commit()
    #
    #     def ping(server, *args, **kwargs):
    #         if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
    #             return None, None
    #         else:
    #             raise
    #
    #     mocked_ping.side_effect = ping
    #
    #     def check_host(host, port, *args, **kwargs):
    #         if host == 'node1':
    #             return True
    #         elif host == 'node2':
    #             return True
    #         elif host == 'node3':
    #             return False
    #         else:
    #             raise
    #
    #     mocked_check_host.side_effect = check_host
    #
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers=self.headers,
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
    #                                                 gate_id='123e4567-e89b-12d3-a456-426655440013',
    #                                                 proxy_server_id=None,
    #                                                 cost=0),
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
    #                                                 gate_id='123e4567-e89b-12d3-a456-426655440012',
    #                                                 proxy_server_id=None,
    #                                                 cost=0)
    #                                        ]})
    #
    #     self.assertIsNone(s1.route)
    #
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     self.assertEqual(None, s3.route.gate)
    #     self.assertEqual(s2, s3.route.proxy_server)
    #     self.assertEqual(1, s3.route.cost)
    #
    #     mocked_threading.Thread.assert_not_called()
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.check_host')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch_scenario3(self, mocked_ping, mocked_check_host, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
    #               dns=s2.name)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
    #               dns=s3.name)
    #
    #     Route(s2, gate=g2, cost=0)
    #     Route(s3, proxy_server=s2, cost=1)
    #     db.session.add_all([s1, s2, s3])
    #     db.session.commit()
    #
    #     def ping(server, *args, **kwargs):
    #         if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
    #             return 1, None
    #
    #     mocked_ping.side_effect = ping
    #
    #     def check_host(host, port, *args, **kwargs):
    #         if host == 'node1':
    #             return True
    #         elif host == 'node2':
    #             return True
    #         elif host == 'node3':
    #             return True
    #
    #     mocked_check_host.side_effect = check_host
    #
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers=self.headers,
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440003',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
    #                                                 gate_id='123e4567-e89b-12d3-a456-426655440011',
    #                                                 proxy_server_id=None,
    #                                                 cost=0)
    #                                        ]})
    #
    #     self.assertIsNone(s1.route)
    #
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     self.assertEqual(g3, s3.route.gate)
    #     self.assertEqual(None, s3.route.proxy_server)
    #     self.assertEqual(0, s3.route.cost)
    #
    #     mocked_threading.Thread.assert_called_once()
    #     args, kwargs = mocked_threading.Thread.call_args
    #     kwargs.pop('target')
    #     self.assertDictEqual(dict(args=(self.app, s2, 'api_1_0.routes'),
    #                               kwargs={'json': {'server_id': str(s1.id),
    #                                                'route_list': [
    #                                                    {'destination_id': str(s3.id),
    #                                                     'proxy_server_id': None,
    #                                                     'gate_id': str(g3.id),
    #                                                     'cost': 0}]},
    #                                       'headers': self.headers}), kwargs)
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.check_host')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch_scenario4(self, mocked_ping, mocked_check_host, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
    #               dns=s2.name)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
    #               dns=s3.name)
    #
    #     db.session.add_all([s1, s2, s3])
    #     db.session.commit()
    #
    #     def ping(server, *args, **kwargs):
    #         if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
    #             return None, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
    #             return None, None
    #
    #     mocked_ping.side_effect = ping
    #
    #     def check_host(host, port, *args, **kwargs):
    #         if host == 'node1':
    #             return True
    #         elif host == 'node2':
    #             return True
    #         elif host == 'node3':
    #             return False
    #
    #     mocked_check_host.side_effect = check_host
    #
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers=self.headers,
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
    #                                                 gate_id='123e4567-e89b-12d3-a456-426655440011',
    #                                                 proxy_server_id=None,
    #                                                 cost=0),
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
    #                                                 gate_id='123e4567-e89b-12d3-a456-426655440013',
    #                                                 proxy_server_id=None,
    #                                                 cost=0)
    #                                        ]})
    #
    #     self.assertIsNone(s1.route)
    #
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     self.assertEqual(None, s3.route.gate)
    #     self.assertEqual(s2, s3.route.proxy_server)
    #     self.assertEqual(1, s3.route.cost)
    #
    #     mocked_threading.Thread.assert_not_called()
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.check_host')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch_scenario5(self, mocked_ping, mocked_check_host, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
    #               dns=s2.name)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
    #               dns=s3.name)
    #
    #     Route(s2, gate=g2, cost=0)
    #     Route(s3, gate=g3, cost=0)
    #     db.session.add_all([s1, s2, s3])
    #     db.session.commit()
    #
    #     def ping(server, *args, **kwargs):
    #         if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
    #             return 0, None
    #
    #     mocked_ping.side_effect = ping
    #
    #     def check_host(host, port, *args, **kwargs):
    #         if host == 'node1':
    #             return True
    #         elif host == 'node2':
    #             return True
    #         elif host == 'node3':
    #             return True
    #
    #     mocked_check_host.side_effect = check_host
    #
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers=self.headers,
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
    #                                                 gate_id=None,
    #                                                 proxy_server_id=None,
    #                                                 cost=None)
    #                                        ]})
    #
    #     self.assertIsNone(s1.route)
    #
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     self.assertEqual(g3, s3.route.gate)
    #     self.assertEqual(None, s3.route.proxy_server)
    #     self.assertEqual(0, s3.route.cost)
    #
    #     mocked_threading.Thread.assert_not_called()
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.check_host')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch_scenario6(self, mocked_ping, mocked_check_host, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
    #               dns=s2.name)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
    #               dns=s3.name)
    #
    #     Route(s2, gate=g2, cost=0)
    #     Route(s3, gate=g3, cost=0)
    #     db.session.add_all([s1, s2, s3])
    #     db.session.commit()
    #
    #     def ping(server, *args, **kwargs):
    #         if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
    #             return None, None
    #
    #     mocked_ping.side_effect = ping
    #
    #     def check_host(host, port, *args, **kwargs):
    #         if host == 'node1':
    #             return True
    #         elif host == 'node2':
    #             return True
    #         elif host == 'node3':
    #             return False
    #
    #     mocked_check_host.side_effect = check_host
    #
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers=self.headers,
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
    #                                                 gate_id=None,
    #                                                 proxy_server_id=None,
    #                                                 cost=None)
    #                                        ]})
    #
    #     self.assertIsNone(s1.route)
    #
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     self.assertEqual(None, s3.route.gate)
    #     self.assertEqual(None, s3.route.proxy_server)
    #     self.assertEqual(None, s3.route.cost)
    #
    #     mocked_threading.Thread.assert_not_called()
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.check_host')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch_scenario7(self, mocked_ping, mocked_check_host, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5001,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5002,
    #               dns=s2.name)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5003,
    #               dns=s3.name)
    #
    #     Route(s2, proxy_server=None, gate=g2, cost=0)
    #     Route(s3, proxy_server=s2, gate=None, cost=1)
    #     db.session.add_all([s1, s2, s3])
    #     db.session.commit()
    #
    #     def ping(server, *args, **kwargs):
    #         if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
    #             return None, None
    #
    #     mocked_ping.side_effect = ping
    #
    #     def check_host(host, port, *args, **kwargs):
    #         if host == 'node1':
    #             return True
    #         elif host == 'node2':
    #             return True
    #         elif host == 'node3':
    #             return False
    #
    #     mocked_check_host.side_effect = check_host
    #
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers=self.headers,
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
    #                                                 gate_id=None,
    #                                                 proxy_server_id=None,
    #                                                 cost=None)
    #                                        ]})
    #
    #     self.assertEqual(0, mocked_ping.call_count)
    #     self.assertEqual(0, mocked_check_host.call_count)
    #     self.assertIsNone(s1.route)
    #
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     self.assertEqual(None, s3.route.gate)
    #     self.assertEqual(None, s3.route.proxy_server)
    #     self.assertEqual(None, s3.route.cost)
    #
    #     mocked_threading.Thread.assert_not_called()
    #
    # @patch('dm.web.api_1_0.urls.use_cases.threading')
    # @patch('dm.web.api_1_0.urls.use_cases.check_host')
    # @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    # def test_routes_patch_scenario8(self, mocked_ping, mocked_check_host, mocked_threading):
    #     s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='node1', me=True)
    #     g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=s1, port=5000,
    #               dns=s1.name)
    #     s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='node2')
    #     g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=s2, port=5000,
    #               dns=s2.name)
    #     s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='node3')
    #     g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=s3, port=5000,
    #               dns=s3.name)
    #
    #     s4 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440004'), name='node4')
    #     g4 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440014'), server=s4, port=5000,
    #               dns=s4.name)
    #
    #     Route(s2, proxy_server=None, gate=g2, cost=0)
    #     Route(s3, proxy_server=s2, gate=None, cost=1)
    #     Route(s4, proxy_server=s2, gate=None, cost=1)
    #     db.session.add_all([s1, s2, s3, s4])
    #     db.session.commit()
    #
    #     def ping(server, *args, **kwargs):
    #         if str(server.id) == '123e4567-e89b-12d3-a456-426655440001':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
    #             return 0, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
    #             return 1, None
    #         elif str(server.id) == '123e4567-e89b-12d3-a456-426655440004':
    #             return None, None
    #         else:
    #             raise
    #
    #     mocked_ping.side_effect = ping
    #
    #     def check_host(host, port, *args, **kwargs):
    #         if host == 'node1':
    #             return True
    #         elif host == 'node2':
    #             return True
    #         elif host == 'node3':
    #             return False
    #         elif host == 'node4':
    #             return False
    #         else:
    #             raise
    #
    #     mocked_check_host.side_effect = check_host
    #
    #     response = self.client.patch(url_for('api_1_0.routes'),
    #                                  headers=self.headers,
    #                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
    #                                        "route_list": [
    #                                            dict(destination_id='123e4567-e89b-12d3-a456-426655440004',
    #                                                 gate_id=None,
    #                                                 proxy_server_id=s3,
    #                                                 cost=1),
    #
    #                                        ]})
    #
    #     self.assertEqual(0, mocked_ping.call_count)
    #     self.assertEqual(0, mocked_check_host.call_count)
    #     self.assertIsNone(s1.route)
    #
    #     self.assertEqual(g2, s2.route.gate)
    #     self.assertEqual(None, s2.route.proxy_server)
    #     self.assertEqual(0, s2.route.cost)
    #
    #     self.assertEqual(g3, s3.route.gate)
    #     self.assertEqual(None, s3.route.proxy_server)
    #     self.assertEqual(0, s3.route.cost)
    #
    #     self.assertEqual(None, s4.route.gate)
    #     self.assertEqual(s3, s4.route.proxy_server)
    #     self.assertEqual(1, s4.route.cost)
    #
    #     mocked_threading.Thread.assert_called_once()
    #     args, kwargs = mocked_threading.Thread.call_args
    #     kwargs.pop('target')
    #     self.assertDictEqual(dict(args=(self.app, s2, 'api_1_0.routes'),
    #                               kwargs={'json': {'server_id': str(s1.id),
    #                                                'route_list': [
    #                                                    {'destination_id': str(s3.id),
    #                                                     'proxy_server_id': None,
    #                                                     'gate_id': str(g3.id),
    #                                                     'cost': 0},
    #                                                    {'destination_id': str(s4.id),
    #                                                     'proxy_server_id': str(s3.id),
    #                                                     'gate_id': None,
    #                                                     'cost': 1}
    #                                                ]},
    #                                       'headers': self.headers}), kwargs)


