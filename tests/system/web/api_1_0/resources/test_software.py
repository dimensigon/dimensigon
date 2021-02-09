import os

from flask import url_for

from dimensigon.domain.entities import Software, Server
from dimensigon.utils.helpers import md5
from dimensigon.web import db
from tests.base import TestResourceBase


class TestSoftwareList(TestResourceBase):

    def fill_database(self):
        self.soft1 = Software(id='11111111-2222-3333-4444-555555550001', name='Dimensigon', version='0.0.1',
                              filename='Dimensigon_0.0.1.tar.gz')
        self.soft2 = Software(id='11111111-2222-3333-4444-555555550002', name='Dimensigon', version='0.0.2',
                              filename='Dimensigon_0.0.2.tar.gz')
        self.soft3 = Software(id='11111111-2222-3333-4444-555555550003', name='python', version='3.6.8',
                              filename='python_3.6.8.x64.tar.gz')
        db.session.add_all([self.soft1, self.soft2, self.soft3])

    def test_get(self):
        resp = self.client.get(url_for('api_1_0.softwarelist'), headers=self.auth.header)

        self.assertListEqual(
            [self.soft1.to_json(no_delete=False),
             self.soft2.to_json(no_delete=False),
             self.soft3.to_json(no_delete=False)], resp.get_json())

    def test_get_with_filter(self):
        resp = self.client.get(url_for('api_1_0.softwarelist', **{'filter[name]': 'Dimensigon'}),
                               headers=self.auth.header)

        self.assertListEqual([self.soft1.to_json(no_delete=False), self.soft2.to_json(no_delete=False)],
                             resp.get_json())

    def test_get_with_filter2(self):
        resp = self.client.get(url_for('api_1_0.softwarelist', **{'filter[version]': '0.0.1,3.6.8'}),
                               headers=self.auth.header)

        self.assertListEqual([self.soft1.to_json(no_delete=False), self.soft3.to_json(no_delete=False)], resp.get_json())

    def test_post(self):
        size = os.path.getsize(__file__)
        checksum = md5(__file__)
        filename = os.path.basename(__file__)
        data = dict(name="Dimensigon", version="0.0.3", family='middleware', file=__file__)
        resp = self.client.post(url_for('api_1_0.softwarelist'), headers=self.auth.header, json=data)

        self.assertEqual(201, resp.status_code)

        soft = Software.query.filter_by(name="Dimensigon", version="0.0.3").one()
        self.assertEqual(size, soft.size)
        self.assertEqual(checksum, soft.checksum)
        self.assertEqual(filename, soft.filename)
        self.assertEqual(1, len(soft.ssas))
        ssa = soft.ssas[0]

        self.assertEqual(os.path.dirname(__file__), ssa.path)
