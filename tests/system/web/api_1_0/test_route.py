import json
import re
import uuid
from unittest import TestCase
from unittest.mock import patch

import responses
from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server, Gate
from dm.domain.entities.route import Route
from dm.web import create_app, db


class TestApiRoutes(TestCase):

    def setUp(self) -> None:
        self.maxDiff = None
        self.app = create_app('test')
        self.app.config['SECURIZER'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        self.s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='server1', me=True)
        self.g1 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440011'), server=self.s1, port=5001,
                       dns=self.s1.name)
        self.s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='server2')
        self.g2 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440012'), server=self.s2, port=5002,
                       dns=self.s2.name)
        Route(self.s2, gate=self.g2, cost=0)
        self.s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='server3')
        self.g3 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440013'), server=self.s3, port=5003,
                       dns=self.s3.name)
        Route(self.s3, gate=self.g3, cost=0)
        self.s4 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440004'), name='server4')
        self.g4 = Gate(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440014'), server=self.s4, port=5001,
                       dns=self.s4.name)
        Route(self.s4, proxy_server=self.s2, cost=1)
        db.session.add_all([self.s1, self.s2, self.s3, self.s4])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_routes_get(self):
        access_token = create_access_token(identity='test')
        response = self.client.get(url_for('api_1_0.routes', _external=False),
                                   headers={"Authorization": f"Bearer {access_token}"})
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

    @patch('dm.web.api_1_0.urls.use_cases.threading')
    @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    def test_routes_patch(self, mocked_ping, mocked_thread):
        mocked_ping.return_value = (None, None)
        access_token = create_access_token(identity='test')
        response = self.client.patch(url_for('api_1_0.routes'),
                                     headers={"Authorization": f"Bearer {access_token}"},
                                     json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
                                           "route_list": [
                                               dict(destination_id='123e4567-e89b-12d3-a456-426655440004',
                                                    gate_id=None,
                                                    proxy_server_id=None,
                                                    cost=None)]})

        # s = Server.query.get('123e4567-e89b-12d3-a456-426655440001')
        # self.assertEqual(None, s.route.gate)
        # self.assertEqual(None, s.route.proxy_server)
        # self.assertEqual(None, s.route.cost)

        # s = Server.query.get('123e4567-e89b-12d3-a456-426655440002')
        self.assertEqual(self.g2, self.s2.route.gate)
        self.assertEqual(None, self.s2.route.proxy_server)
        self.assertEqual(0, self.s2.route.cost)

        # s = Server.query.get('123e4567-e89b-12d3-a456-426655440003')
        self.assertEqual(self.g3, self.s3.route.gate)
        self.assertEqual(None, self.s3.route.proxy_server)
        self.assertEqual(0, self.s3.route.cost)

        # s = Server.query.get('123e4567-e89b-12d3-a456-426655440004')
        self.assertEqual(None, self.s4.route.gate)
        self.assertEqual(None, self.s4.route.proxy_server)
        self.assertEqual(None, self.s4.route.cost)

        self.assertEqual(1, mocked_thread.Thread.call_count)

    @patch('dm.web.api_1_0.urls.use_cases.threading')
    @patch('dm.use_cases.interactor.ping')
    @responses.activate
    def test_routes_post_broken_route_2_4(self, mocked_ping, mocked_threading):
        def callback(request):

            if request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440002').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440002',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                gate_id='123e4567-e89b-12d3-a456-426655440011', proxy_server_id=None, cost=0),
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440003',
                                gate_id=None,
                                proxy_server_id='123e4567-e89b-12d3-a456-426655440001',
                                cost=1),
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440004',
                                gate_id='123e4567-e89b-12d3-a456-426655440014', proxy_server_id=None, cost=None),
                       ]}
            if request.url == Server.query.get('123e4567-e89b-12d3-a456-426655440003').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440003',
                       "route_list": [
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440001',
                                gate_id='123e4567-e89b-12d3-a456-426655440011', proxy_server_id=None, cost=0),
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440002',
                                gate_id=None,
                                proxy_server_id='123e4567-e89b-12d3-a456-426655440001', cost=1),
                           dict(destination_id='123e4567-e89b-12d3-a456-426655440004',
                                gate_id='123e4567-e89b-12d3-a456-426655440014', proxy_server_id=None, cost=0),
                       ]}
            return 200, {}, json.dumps(msg)

        responses.add_callback(responses.GET, re.compile('^https?://.*$'), callback=callback,
                               content_type='application/json')

        def ping(server):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440004':
                return None, None

        mocked_ping.side_effect = ping
        access_token = create_access_token(identity='test')
        response = self.client.post(url_for('api_1_0.routes', _external=False),
                                    headers={"Authorization": f"Bearer {access_token}"},
                                    json={})

        # r = Route.query.filter_by(destination_id='123e4567-e89b-12d3-a456-426655440001').one()
        self.assertIsNone(None, self.s1.route)

        # r = Route.query.filter_by(destination_id='123e4567-e89b-12d3-a456-426655440002').one()
        self.assertEqual(self.g2, self.s2.route.gate)
        self.assertEqual(None, self.s2.route.proxy_server)
        self.assertEqual(0, self.s2.route.cost)

        # r = Route.query.filter_by(destination_id='123e4567-e89b-12d3-a456-426655440003').one()
        self.assertEqual(self.g3, self.s3.route.gate)
        self.assertEqual(None, self.s3.route.proxy_server)
        self.assertEqual(0, self.s3.route.cost)

        # r = Route.query.filter_by(destination_id='123e4567-e89b-12d3-a456-426655440004').one()
        self.assertEqual(None, self.s4.route.gate)
        self.assertEqual('123e4567-e89b-12d3-a456-426655440003', str(self.s4.route.proxy_server.id))
        self.assertEqual(1, self.s4.route.cost)
