from unittest import TestCase

from flask import url_for

from dimensigon.domain.entities import Server, Log
from dimensigon.web import db, errors
from tests.base import LockBypassMixin, OneNodeMixin, ValidateResponseMixin


class TestLogList(LockBypassMixin, OneNodeMixin, TestCase):
    initials = dict(server=False, action_template=False)

    def fill_database(self):
        self.dest1 = Server('dest1', port=8000)
        self.dest2 = Server('dest2', port=8000)
        self.log = Log(source_server=self.s1, target='/var/log/log1.log', destination_server=self.dest1)
        db.session.add_all([self.dest1, self.dest2, self.log])
        db.session.commit()

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.loglist'), headers=self.auth.header)
        self.assertListEqual([self.log.to_json()], resp.get_json())

        log = Log(source_server=Server.get_current(), target='/access.log', destination_server=self.dest2)
        db.session.add(log)
        db.session.commit()

        # test with filter
        resp = self.client.get(url_for('api_1_0.loglist') + "?filter[target]=/access.log",
                               headers=self.auth.header)
        self.assertListEqual([log.to_json()], resp.get_json())

        # test with filter on a server
        resp = self.client.get(url_for('api_1_0.loglist') + f"?filter[dst_server_id]={self.dest1.id}",
                               headers=self.auth.header)
        self.assertListEqual([self.log.to_json()], resp.get_json())

    def test_post(self):
        new_log_json = {"src_server_id": str(self.dest1.id),
                        "target": '/var/log',
                        "exclude": 'system.log'}

        resp = self.client.post(url_for('api_1_0.loglist'), headers=self.auth.header,
                                json=new_log_json)
        self.assertEqual(400, resp.status_code)

        new_log_json = {"src_server_id": str(self.dest1.id),
                        "target": '/var/log',
                        "exclude": 'system.log',
                        "dst_server_id": str(self.dest1.id)}

        resp = self.client.post(url_for('api_1_0.loglist'), headers=self.auth.header,
                                json=new_log_json)
        self.assertEqual(400, resp.status_code)
        self.assertDictEqual({'error': 'source and destination must be different'}, resp.get_json())

        new_log_json = {"src_server_id": str(self.dest1.id),
                        "target": '/var/log',
                        "exclude": 'system.log',
                        "dst_server_id": str(self.dest2.id)}

        resp = self.client.post(url_for('api_1_0.loglist'), headers=self.auth.header,
                                json=new_log_json)
        self.assertEqual(201, resp.status_code)
        log = Log.query.get(resp.get_json().get('id'))
        self.assertEqual(self.dest1, log.source_server)
        self.assertEqual('/var/log', log.target)
        self.assertIsNone(log.include)
        self.assertEqual('system.log', log.exclude)
        self.assertEqual(self.dest2, log.destination_server)
        self.assertFalse(log.recursive)
        self.assertIsNone(log.dest_folder)


class TestLogResource(LockBypassMixin, OneNodeMixin, ValidateResponseMixin, TestCase):

    def fill_database(self):
        """Create and configure a new app instance for each test."""
        self.dest1 = Server('dest1', port=8000)
        self.dest2 = Server('dest2', port=8000)
        self.log = Log(source_server=self.s1, target='/var/log/log1.log',
                       destination_server=self.dest1)
        db.session.add_all([self.dest1, self.dest2, self.log])

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header)
        self.assertEqual(200, resp.status_code)

        self.assertEqual(self.log.to_json(), resp.get_json())

        resp = self.client.get(url_for('api_1_0.logresource', log_id='aaaa'), headers=self.auth.header)
        self.assertEqual(404, resp.status_code)

    def test_patch(self):
        patch_log_json = {"src_server_id": str(self.dest2.id), }

        resp = self.client.patch(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header,
                                 json=patch_log_json)
        self.assertEqual(400, resp.status_code)

        patch_log_json = {"dest_folder": '/dest'}

        self.assertIsNone(self.log.dest_folder)
        resp = self.client.patch(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header,
                                 json=patch_log_json)
        self.validate_error_response(resp,
                                     errors.InvalidValue("property dest_folder can not be set with REPO_MIRROR mode"))

        patch_log_json = {"dest_folder": '/dest', 'mode': 'FOLDER'}
        resp = self.client.patch(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header,
                                 json=patch_log_json)
        self.assertEqual(204, resp.status_code)
        db.session.refresh(self.log)
        self.assertEqual('/dest', self.log.dest_folder)

        resp = self.client.patch(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header,
                                 json={"dest_folder": '/dest'})
        self.assertEqual(202, resp.status_code)

    # def test_delete(self):
    #     resp = self.client.delete(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header)
    #     self.assertEqual(204, resp.status_code)
    #
    #     self.assertEqual(0, Log.query.count())
    #
    #     resp = self.client.delete(url_for('api_1_0.logresource', log_id=str(self.log.id)), headers=self.auth.header)
    #     self.assertEqual(404, resp.status_code)
