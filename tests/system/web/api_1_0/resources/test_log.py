from flask import url_for
from flask_jwt_extended import create_access_token

from dm.domain.entities import Server, Log
from dm.domain.entities.bootstrap import set_initial
from dm.network.auth import HTTPBearerAuth
from dm.web import create_app, db
from tests.helpers import TestCaseLockBypass


class Testloglist(TestCaseLockBypass):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()
        set_initial()
        self.node1 = Server('node1', port=8000)
        self.node2 = Server('node2', port=8000)
        self.log = Log(source_server=Server.get_current(), target='/var/log/log1.log', destination_server=self.node1)
        db.session.add_all([self.node1, self.node2, self.log])
        db.session.commit()

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.loglist'), headers=self.auth.header)
        self.assertListEqual([self.log.to_json()], resp.get_json())

        log = Log(source_server=Server.get_current(), target='/access.log', destination_server=self.node2)
        db.session.add(log)
        db.session.commit()

        # test with filter
        resp = self.client.get(url_for('api_1_0.loglist') + "?filter[target]=/access.log",
                               headers=self.auth.header)
        self.assertListEqual([log.to_json()], resp.get_json())

        # test with filter on a server
        resp = self.client.get(url_for('api_1_0.loglist') + f"?filter[dst_server_id]={self.node1.id}",
                               headers=self.auth.header)
        self.assertListEqual([self.log.to_json()], resp.get_json())

    def test_post(self):
        new_log_json = {"src_server_id": str(self.node1.id),
                        "target": '/var/log',
                        "exclude": 'system.log'}

        resp = self.client.post(url_for('api_1_0.loglist'), headers=self.auth.header,
                                json=new_log_json)
        self.assertEqual(400, resp.status_code)

        new_log_json = {"src_server_id": str(self.node1.id),
                        "target": '/var/log',
                        "exclude": 'system.log',
                        "dst_server_id": str(self.node1.id)}

        resp = self.client.post(url_for('api_1_0.loglist'), headers=self.auth.header,
                                json=new_log_json)
        self.assertEqual(400, resp.status_code)
        self.assertDictEqual({'error': 'source and destination must be different'}, resp.get_json())

        new_log_json = {"src_server_id": str(self.node1.id),
                        "target": '/var/log',
                        "exclude": 'system.log',
                        "dst_server_id": str(self.node2.id)}

        resp = self.client.post(url_for('api_1_0.loglist'), headers=self.auth.header,
                                json=new_log_json)
        self.assertEqual(201, resp.status_code)
        log = Log.query.get(resp.get_json().get('log_id'))
        self.assertEqual(self.node1, log.source_server)
        self.assertEqual('/var/log', log.target)
        self.assertIsNone(log.include)
        self.assertEqual('system.log', log.exclude)
        self.assertEqual(self.node2, log.destination_server)
        self.assertFalse(log.recursive)
        self.assertIsNone(log.dest_folder)


class TestLogResource(TestCaseLockBypass):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create the app with common test config
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        self.auth = HTTPBearerAuth(create_access_token('00000000-0000-0000-0000-000000000001'))
        db.create_all()
        set_initial()
        self.node1 = Server('node1', port=8000)
        self.node2 = Server('node2', port=8000)
        self.log = Log(source_server=Server.get_current(), target='/var/log/log1.log',
                       destination_server=self.node1)
        db.session.add_all([self.node1, self.node2, self.log])
        db.session.commit()

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header)
        self.assertEqual(200, resp.status_code)

        self.assertEqual(self.log.to_json(), resp.get_json())

        resp = self.client.get(url_for('api_1_0.logresource', log_id='aaaa'), headers=self.auth.header)
        self.assertEqual(404, resp.status_code)

    def test_patch(self):
        patch_log_json = {"src_server_id": str(self.node2.id), }

        resp = self.client.patch(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header,
                                 json=patch_log_json)
        self.assertEqual(400, resp.status_code)

        patch_log_json = {"dest_folder": '/dest'}

        self.assertIsNone(self.log.dest_folder)
        resp = self.client.patch(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header,
                                 json=patch_log_json)
        self.assertEqual(204, resp.status_code)
        db.session.refresh(self.log)
        self.assertEqual('/dest', self.log.dest_folder)

        resp = self.client.patch(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header,
                                 json=patch_log_json)
        self.assertEqual(202, resp.status_code)

    # def test_delete(self):
    #     resp = self.client.delete(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header)
    #     self.assertEqual(204, resp.status_code)
    #
    #     self.assertEqual(0, Log.query.count())
    #
    #     resp = self.client.delete(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header)
    #     self.assertEqual(404, resp.status_code)
