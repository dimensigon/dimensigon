import os
import uuid
from unittest import TestCase, mock

from flask import url_for

from dm.domain.entities import Software, SoftwareFamily
from dm.network.gateway import unpack_msg, pack_msg
from dm.utils.helpers import md5
from dm.web import create_app, db, set_variables
from tests.helpers import authorization_header


class TestSoftwareList(TestCase):

    def setUp(self) -> None:
        self.app = create_app('test')
        db.create_all(app=self.app)
        set_variables(self.app)
        Software.metadata.tables['D_software']._columns['id'].default.arg = mock.MagicMock(
            side_effect=[uuid.UUID('11111111-2222-3333-4444-555555550001'),
                         uuid.UUID('11111111-2222-3333-4444-555555550002'),
                         uuid.UUID('11111111-2222-3333-4444-555555550003'),
                         uuid.UUID('11111111-2222-3333-4444-555555550004')])
        with self.app.app_context():
            soft1 = Software(name='Dimensigon', version='0.0.1', family=SoftwareFamily.MIDDLEWARE,
                             filename='Dimensigon_0.0.1.tar.gz')
            soft2 = Software(name='Dimensigon', version='0.0.2', family=SoftwareFamily.MIDDLEWARE,
                             filename='Dimensigon_0.0.2.tar.gz')
            soft3 = Software(name='python', version='3.6.8', family=SoftwareFamily.MIDDLEWARE,
                             filename='python_3.6.8.x64.tar.gz')
            db.session.add_all([soft1, soft2, soft3])
            db.session.commit()
            self.soft1_json = soft1.to_json()
            self.soft2_json = soft2.to_json()
            self.soft3_json = soft3.to_json()

    def test_get(self):
        with self.app.app_context():
            client = self.app.test_client()
            resp = client.get(url_for('api_1_0.softwarelist'), headers=authorization_header())

            self.assertListEqual(
                [self.soft1_json, self.soft2_json, self.soft3_json], unpack_msg(resp.get_json()))

    def test_get_with_filter(self):
        with self.app.app_context():
            client = self.app.test_client()
            resp = client.get(url_for('api_1_0.softwarelist', **{'filter[name]': 'Dimensigon'}),
                              headers=authorization_header())

            self.assertListEqual([self.soft1_json, self.soft2_json], unpack_msg(resp.get_json()))

    def test_get_with_filter2(self):
        with self.app.app_context():
            client = self.app.test_client()
            resp = client.get(url_for('api_1_0.softwarelist', **{'filter[version]': '0.0.1,3.6.8'}),
                              headers=authorization_header())

            self.assertListEqual([self.soft1_json, self.soft3_json], unpack_msg(resp.get_json()))

    def test_post_without_server(self):
        with self.app.app_context():
            client = self.app.test_client()
            data = dict(name="Dimensigon", version="0.0.3", family='middleware')
            packed_msg = pack_msg(data)
            resp = client.post(url_for('api_1_0.softwarelist'), headers=authorization_header(), json=packed_msg)

            self.assertEqual(201, resp.status_code)
            self.assertDictEqual({'software_id': '11111111-2222-3333-4444-555555550004'}, unpack_msg(resp.get_json()))

    def test_post_with_server(self):
        with self.app.app_context():
            client = self.app.test_client()
            size = os.path.getsize(__file__)
            checksum = md5(__file__)
            filename = os.path.basename(__file__)
            data = dict(name="Dimensigon", version="0.0.3", family='middleware', server_id=str(self.app.server_id),
                        file=__file__)
            packed_msg = pack_msg(data)
            resp = client.post(url_for('api_1_0.softwarelist'), headers=authorization_header(), json=packed_msg)

            self.assertEqual(201, resp.status_code)
            self.assertDictEqual({'software_id': '11111111-2222-3333-4444-555555550004'}, unpack_msg(resp.get_json()))

            soft = Software.query.get('11111111-2222-3333-4444-555555550004')
            self.assertEqual(size, soft.size)
            self.assertEqual(checksum, soft.checksum)
            self.assertEqual(filename, soft.filename)
