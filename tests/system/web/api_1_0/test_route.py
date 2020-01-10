import ipaddress
import json
import os
import uuid
from unittest import TestCase
from unittest.mock import patch

import requests
from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server
from dm.network.gateway import unpack_msg, pack_msg
from dm.web import create_app, db, set_variables


class TestApiRoutes(TestCase):

    def setUp(self) -> None:
        self.maxDiff = None
        self.app1 = create_app(dict(TESTING=True,
                                    SERVER_NAME='server1',
                                    PORT=5001,
                                    SQLALCHEMY_DATABASE_URI='sqlite://',
                                    DM_PLAIN_DATA=True,
                                    SQLALCHEMY_TRACK_MODIFICATIONS=False,
                                    SECRET_KEY='my precious key'))

        with self.app1.app_context():
            db.create_all()
            self.s1 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440001'), name='server1',
                             ip=ipaddress.IPv4Address('127.0.0.1'),
                             port=5001,
                             mesh_best_route=[],
                             mesh_alt_route=[],
                             gateway=None,
                             cost=None,
                             )
            self.s2 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440002'), name='server2',
                             ip=ipaddress.IPv4Address('127.0.0.1'),
                             port=5002,
                             mesh_best_route=[],
                             mesh_alt_route=[],
                             gateway=None,
                             cost=0,
                             )
            self.s3 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440003'), name='server3',
                             ip=ipaddress.IPv4Address('127.0.0.1'),
                             port=5003,
                             mesh_best_route=[],
                             mesh_alt_route=[],
                             gateway=None,
                             cost=0,
                             )
            self.s4 = Server(id=uuid.UUID('123e4567-e89b-12d3-a456-426655440004'), name='server4',
                             ip=ipaddress.IPv4Address('127.0.0.1'),
                             port=5004,
                             mesh_best_route=[uuid.UUID('123e4567-e89b-12d3-a456-426655440002')],
                             mesh_alt_route=[uuid.UUID('123e4567-e89b-12d3-a456-426655440003')],
                             gateway=self.s2,
                             cost=1,
                             )
            db.session.add_all([self.s1, self.s2, self.s3, self.s4])
            db.session.commit()
            self.response = {'server_id': '123e4567-e89b-12d3-a456-426655440001',
                             'server_list': [self.s2.to_json(), self.s3.to_json(), self.s4.to_json()]}
            set_variables()

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
            data = unpack_msg(response.get_json())
            self.assertDictEqual({'server_id': str(self.s1.id),
                                  'server_list': [self.s2.to_json(), self.s3.to_json(), self.s4.to_json()]}, data)

    def test_routes_patch(self):
        cli1 = self.app1.test_client()
        with self.app1.app_context():
            access_token = create_access_token(identity='test')
            response = cli1.patch(url_for('api_1_0.routes', _external=False),
                                  headers={"Authorization": f"Bearer {access_token}"},
                                  json=pack_msg({"server_id": str(self.s2.id),
                                                 "server_list": [dict(id=str(self.s4.id), gateway=None, cost=None)]}))

            self.assertEqual(None, Server.query.get(self.s1.id).gateway)
            self.assertEqual(None, Server.query.get(self.s1.id).cost)
            self.assertEqual(None, Server.query.get(self.s2.id).gateway)
            self.assertEqual(0, Server.query.get(self.s2.id).cost)
            self.assertEqual(None, Server.query.get(self.s3.id).gateway)
            self.assertEqual(0, Server.query.get(self.s3.id).cost)
            self.assertEqual(None, Server.query.get(self.s4.id).gateway)
            self.assertEqual(None, Server.query.get(self.s4.id).cost)

    @patch('dm.use_cases.interactor.ping')
    @patch('dm.use_cases.interactor.requests.get')
    def test_routes_post_broken_route_2_4(self, mocked_get, mocked_ping):
        def get(url, **kwargs):

            if url == self.s2.url('api_1_0.routes'):
                msg = pack_msg({"server_id": str(self.s2.id),
                                "server_list": [
                                    dict(id=str(self.s1.id), gateway=None, cost=0),
                                    dict(id=str(self.s3.id), gateway=str(self.s1.id), cost=1),
                                    dict(id=str(self.s4.id), gateway=None, cost=None),
                                ]})
            if url == self.s3.url('api_1_0.routes'):
                msg = pack_msg({"server_id": str(self.s3.id),
                                "server_list": [
                                    dict(id=str(self.s1.id), gateway=None, cost=0),
                                    dict(id=str(self.s2.id), gateway=str(self.s1.id), cost=1),
                                    dict(id=str(self.s4.id), gateway=None, cost=0),
                                ]})
            resp = requests.Response()
            resp.status_code = 200
            resp.url = url
            resp.headers = {'USER-AGENT': 'werkzeug/0.16.0', 'CONTENT-TYPE': 'application/json'}
            resp._content = str(json.dumps(msg)).encode()
            return resp

        def ping(server):
            if server.id == self.s2.id:
                return 0, None
            elif server.id == self.s3.id:
                return 0, None
            elif server.id == self.s4.id:
                return None, None

        mocked_get.side_effect = get
        mocked_ping.side_effect = ping
        cli1 = self.app1.test_client()
        with self.app1.app_context():
            access_token = create_access_token(identity='test')
            response = cli1.post(url_for('api_1_0.routes', _external=False),
                                 headers={"Authorization": f"Bearer {access_token}"},
                                 json=pack_msg({}))

            s = Server.query.get(self.s1.id)
            self.assertEqual(None, s.gateway)
            self.assertEqual(None, s.cost)

            s = Server.query.get(self.s2.id)
            self.assertEqual(None, s.gateway)
            self.assertEqual(0, s.cost)

            s = Server.query.get(self.s3.id)
            self.assertEqual(None, s.gateway)
            self.assertEqual(0, s.cost)

            s = Server.query.get(self.s4.id)
            self.assertEqual(self.s3.id, s.gateway.id)
            self.assertEqual(1, s.cost)
