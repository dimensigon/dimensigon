import os
import uuid
from unittest import TestCase, mock

from flask import url_for

from dm.domain.entities import Software, Server
from dm.domain.entities.bootstrap import set_initial
from dm.utils.helpers import md5
from dm.web import create_app, db
from tests.helpers import authorization_header


class TestSoftwareList(TestCase):

    def setUp(self) -> None:
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        set_initial()
        soft1 = Software(id='11111111-2222-3333-4444-555555550001', name='Dimensigon', version='0.0.1',
                         filename='Dimensigon_0.0.1.tar.gz')
        soft2 = Software(id='11111111-2222-3333-4444-555555550002', name='Dimensigon', version='0.0.2',
                         filename='Dimensigon_0.0.2.tar.gz')
        soft3 = Software(id='11111111-2222-3333-4444-555555550003', name='python', version='3.6.8',
                         filename='python_3.6.8.x64.tar.gz')
        db.session.add_all([soft1, soft2, soft3])
        db.session.commit()
        self.soft1_json = soft1.to_json()
        self.soft2_json = soft2.to_json()
        self.soft3_json = soft3.to_json()

        Software.metadata.tables['D_software']._columns['id'].default.arg = mock.MagicMock(
            return_value=uuid.UUID('11111111-2222-3333-4444-555555550004'))

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.softwarelist'), headers=authorization_header())

        self.assertListEqual(
            [self.soft1_json, self.soft2_json, self.soft3_json], resp.get_json())

    def test_get_with_filter(self):
        resp = self.client.get(url_for('api_1_0.softwarelist', **{'filter[name]': 'Dimensigon'}),
                               headers=authorization_header())

        self.assertListEqual([self.soft1_json, self.soft2_json], resp.get_json())

    def test_get_with_filter2(self):
        resp = self.client.get(url_for('api_1_0.softwarelist', **{'filter[version]': '0.0.1,3.6.8'}),
                               headers=authorization_header())

        self.assertListEqual([self.soft1_json, self.soft3_json], resp.get_json())

    def test_post_without_server(self):
        Software.metadata.tables['D_software']._columns['id'].default.arg = mock.MagicMock(
            side_effect=[uuid.UUID('11111111-2222-3333-4444-555555550004')])
        data = dict(name="Dimensigon", version="0.0.3", family='middleware')
        resp = self.client.post(url_for('api_1_0.softwarelist'), headers=authorization_header(), json=data)

        self.assertEqual(201, resp.status_code)
        self.assertDictEqual({'software_id': '11111111-2222-3333-4444-555555550004'}, resp.get_json())

    def test_post_with_server(self):
        size = os.path.getsize(__file__)
        checksum = md5(__file__)
        filename = os.path.basename(__file__)
        data = dict(name="Dimensigon", version="0.0.3", family='middleware', server_id=str(Server.get_current().id),
                    file=__file__)
        resp = self.client.post(url_for('api_1_0.softwarelist'), headers=authorization_header(), json=data)

        self.assertEqual(201, resp.status_code)
        self.assertDictEqual({'software_id': '11111111-2222-3333-4444-555555550004'}, resp.get_json())

        soft = Software.query.get('11111111-2222-3333-4444-555555550004')
        self.assertEqual(size, soft.size)
        self.assertEqual(checksum, soft.checksum)
        self.assertEqual(filename, soft.filename)
