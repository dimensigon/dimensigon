import ipaddress
import json
import uuid
from unittest import TestCase
from unittest.mock import patch

import requests
from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server
from dm.domain.entities.route import Route
from dm.web import create_app, db


class TestApiRoutes(TestCase):

    def setUp(self) -> None:
        self.maxDiff = None
        self.app1 = create_app(dict(TESTING=True,
                                    SERVER_NAME='server1',
                                    PORT=5001,
                                    SQLALCHEMY_DATABASE_URI='sqlite://',
                                    DM_PLAIN_DATA=True,
                                    SQLALCHEMY_TRACK_MODIFICATIONS=False,
                                    SECRET_KEY='my precious key',
                                    SSL_VERIFY=False)
                               )

        with self.app1.app_context():
            db.create_all()
            s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='server1',
                        ip=ipaddress.IPv4Address('127.0.0.1'),
                        port=5001,
                        gateway=None,
                        cost=None,
                        me=True
                        )
            s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='server2',
                        ip=ipaddress.IPv4Address('127.0.0.1'),
                        port=5002,
                        gateway=None,
                        cost=0,
                        )
            s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='server3',
                        ip=ipaddress.IPv4Address('127.0.0.1'),
                        port=5003,
                        gateway=None,
                        cost=0,
                        )
            s4 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440004'), name='server4',
                        ip=ipaddress.IPv4Address('127.0.0.1'),
                        port=5004,
                        gateway=s2,
                        cost=1,
                        )
            db.session.add_all([s1, s2, s3, s4])
            db.session.commit()

    # def tearDown(self) -> None:
    #     with self.app1.app_context():
    #         self.app1.queue.stop()
    #         db.drop_all()

    def test_routes_get(self):
        cli1 = self.app1.test_client()
        with self.app1.app_context():
            access_token = create_access_token(identity='test')
            response = cli1.get(url_for('api_1_0.routes', _external=False),
                                headers={"Authorization": f"Bearer {access_token}"})
            data = response.get_json()
            self.assertDictEqual({'server_id': '123e4567-e89b-12d3-a456-426655440001',
                                  'route_list': [
                                      dict(destination='123e4567-e89b-12d3-a456-426655440002', gateway=None, cost=0),
                                      dict(destination='123e4567-e89b-12d3-a456-426655440003', gateway=None, cost=0),
                                      dict(destination='123e4567-e89b-12d3-a456-426655440004',
                                           gateway='123e4567-e89b-12d3-a456-426655440002', cost=1)]}, data)

    @patch('dm.web.api_1_0.urls.use_cases.threading')
    @patch('dm.web.api_1_0.urls.use_cases.ping_server')
    def test_routes_patch(self, mocked_ping, mocked_thread):
        mocked_ping.return_value = (None, None)
        cli1 = self.app1.test_client()
        with self.app1.app_context():
            access_token = create_access_token(identity='test')
            response = cli1.patch(url_for('api_1_0.routes'),
                                  headers={"Authorization": f"Bearer {access_token}"},
                                  json={"server_id": '123e4567-e89b-12d3-a456-426655440002',
                                        "route_list": [
                                            dict(destination='123e4567-e89b-12d3-a456-426655440004',
                                                 gateway=None,
                                                 cost=None)]})

            s = Server.query.get('123e4567-e89b-12d3-a456-426655440001')
            self.assertEqual(None, s.route.gateway)
            self.assertEqual(None, s.route.cost)

            s = Server.query.get('123e4567-e89b-12d3-a456-426655440002')
            self.assertEqual(None, s.route.gateway)
            self.assertEqual(0, s.route.cost)

            s = Server.query.get('123e4567-e89b-12d3-a456-426655440003')
            self.assertEqual(None, s.route.gateway)
            self.assertEqual(0, s.route.cost)

            s = Server.query.get('123e4567-e89b-12d3-a456-426655440004')
            self.assertEqual(None, s.route.gateway)
            self.assertEqual(None, s.route.cost)

            self.assertEqual(1, mocked_thread.Thread.call_count)

    @patch('dm.use_cases.interactor.ping')
    @patch('dm.use_cases.interactor.requests.get')
    def test_routes_post_broken_route_2_4(self, mocked_get, mocked_ping):
        def get(url, **kwargs):

            if url == Server.query.get('123e4567-e89b-12d3-a456-426655440002').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440002',
                       "route_list": [
                           dict(destination='123e4567-e89b-12d3-a456-426655440001', gateway=None, cost=0),
                           dict(destination='123e4567-e89b-12d3-a456-426655440003',
                                gateway='123e4567-e89b-12d3-a456-426655440001', cost=1),
                           dict(destination='123e4567-e89b-12d3-a456-426655440004', gateway=None, cost=None),
                       ]}
            if url == Server.query.get('123e4567-e89b-12d3-a456-426655440003').url('api_1_0.routes'):
                msg = {"server_id": '123e4567-e89b-12d3-a456-426655440003',
                       "route_list": [
                           dict(destination='123e4567-e89b-12d3-a456-426655440001', gateway=None, cost=0),
                           dict(destination='123e4567-e89b-12d3-a456-426655440002',
                                gateway='123e4567-e89b-12d3-a456-426655440001', cost=1),
                           dict(destination='123e4567-e89b-12d3-a456-426655440004', gateway=None, cost=0),
                       ]}
            resp = requests.Response()
            resp.status_code = 200
            resp.url = url
            resp.headers = {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json'}
            resp._content = str(json.dumps(msg)).encode()
            return resp

        def ping(server):
            if str(server.id) == '123e4567-e89b-12d3-a456-426655440002':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440003':
                return 0, None
            elif str(server.id) == '123e4567-e89b-12d3-a456-426655440004':
                return None, None

        mocked_get.side_effect = get
        mocked_ping.side_effect = ping
        cli1 = self.app1.test_client()
        with self.app1.app_context():
            access_token = create_access_token(identity='test')
            response = cli1.post(url_for('api_1_0.routes', _external=False),
                                 headers={"Authorization": f"Bearer {access_token}"},
                                 json={})

            r = Route.query.filter_by(destination_id='123e4567-e89b-12d3-a456-426655440001').one()
            self.assertEqual(None, r.gateway)
            self.assertEqual(None, r.cost)

            r = Route.query.filter_by(destination_id='123e4567-e89b-12d3-a456-426655440002').one()
            self.assertEqual(None, r.gateway)
            self.assertEqual(0, r.cost)

            r = Route.query.filter_by(destination_id='123e4567-e89b-12d3-a456-426655440003').one()
            self.assertEqual(None, r.gateway)
            self.assertEqual(0, r.cost)

            r = Route.query.filter_by(destination_id='123e4567-e89b-12d3-a456-426655440004').one()
            self.assertEqual('123e4567-e89b-12d3-a456-426655440003', str(r.gateway.id))
            self.assertEqual(1, r.cost)
