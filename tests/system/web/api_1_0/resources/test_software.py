import os

from flask import url_for
from flask_jwt_extended import create_access_token

from dimensigon.domain.entities import Software, Server, User
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.network.auth import HTTPBearerAuth
from dimensigon.utils.helpers import md5
from dimensigon.web import create_app, db
from tests.helpers import TestCaseLockBypass


class TestSoftwareList(TestCaseLockBypass):

    def setUp(self) -> None:
        self.app = create_app('test')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        set_initial()
        self.auth = HTTPBearerAuth(create_access_token(User.get_by_user('root').id))
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

    def tearDown(self) -> None:
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.softwarelist'), headers=self.auth.header)

        self.assertListEqual(
            [self.soft1_json, self.soft2_json, self.soft3_json], resp.get_json())

    def test_get_with_filter(self):
        resp = self.client.get(url_for('api_1_0.softwarelist', **{'filter[name]': 'Dimensigon'}),
                               headers=self.auth.header)

        self.assertListEqual([self.soft1_json, self.soft2_json], resp.get_json())

    def test_get_with_filter2(self):
        resp = self.client.get(url_for('api_1_0.softwarelist', **{'filter[version]': '0.0.1,3.6.8'}),
                               headers=self.auth.header)

        self.assertListEqual([self.soft1_json, self.soft3_json], resp.get_json())

    def test_post(self):
        size = os.path.getsize(__file__)
        checksum = md5(__file__)
        filename = os.path.basename(__file__)
        data = dict(name="Dimensigon", version="0.0.3", family='middleware', server_id=str(Server.get_current().id),
                    file=__file__)
        resp = self.client.post(url_for('api_1_0.softwarelist'), headers=self.auth.header, json=data)

        self.assertEqual(201, resp.status_code)

        soft = Software.query.filter_by(name="Dimensigon", version="0.0.3").one()
        self.assertEqual(size, soft.size)
        self.assertEqual(checksum, soft.checksum)
        self.assertEqual(filename, soft.filename)
        self.assertEqual(1, len(soft.ssas))
        ssa = soft.ssas[0]

        self.assertEqual(os.path.dirname(__file__), ssa.path)
