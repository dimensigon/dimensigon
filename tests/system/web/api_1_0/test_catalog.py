import base64
import copy
import datetime
import pickle
from unittest import TestCase, mock

from flask import url_for
from flask_jwt_extended import create_access_token

import config
from dm.web import create_app, repo_manager


def get_now(**kwargs):
    return datetime.datetime(2020, 1, 1, 10, 10, 10, 0) + datetime.timedelta(**kwargs)


class TestCatalog(TestCase):

    def setUp(self):
        """Create and configure a new app instance for each test."""
        # create a temporary file to isolate the database for each test
        # create the app with common test config
        self.app = create_app('dev')
        self.app_context = self.app.app_context()
        self.app_context.push()
        # db.create_all()
        # Role.insert_roles()
        self.client = self.app.test_client()
        self.access_token = create_access_token(identity='test')

    def test_catalog_full(self):
        self.maxDiff = None
        headers = {'Authorization': f'Bearer {self.access_token}'}
        resp = self.client.get(url_for('api_1_0.catalog', data_mark='00010101000000000000'), headers=headers)
        json = resp.get_json()
        data_encoded = json.get('data')
        data = pickle.loads(base64.b64decode(data_encoded))

        expected_data = copy.deepcopy(config.data)
        expected_data.pop('CatalogRepo')
        self.assertDictEqual(expected_data, data)

    def test_catalog_delta(self):
        self.maxDiff = None

        with mock.patch('dm.domain.catalog_manager.get_now', side_effect=get_now):
            with self.app_context:
                s = repo_manager.ServerRepo.find('bbbbbbbb-1234-5678-1234-56781234bbb1')
                s.port = 8080
                repo_manager.ServerRepo.update(s)

        headers = {'Authorization': f'Bearer {self.access_token}'}
        resp = self.client.get(url_for('api_1_0.catalog', data_mark='20190101000530100000'), headers=headers)

        json = resp.get_json()
        data_encoded = json.get('data')
        data = pickle.loads(base64.b64decode(data_encoded))

        expected_data = {'ServerRepo': [
            dict(id='bbbbbbbb-1234-5678-1234-56781234bbb1', name='localhost.localdomain', ip='127.0.0.1', port=8080,
                 birth=None,
                 keep_alive=None, available=True, granules=[], route=[], alt_route=[],
                 data_mark='20200101101010000000')]}
        self.assertDictEqual(expected_data, data)

    def test_catalog_wrong_datamark(self):
        self.maxDiff = None
        headers = {'Authorization': f'Bearer {self.access_token}'}
        resp = self.client.get(url_for('api_1_0.catalog', data_mark='54'), headers=headers)
        json = resp.get_json()
        self.assertEqual(400, resp.status_code)
        self.assertDictEqual({'error': "Invalid Data Mark: time data '54' does not match format '%Y%m%d%H%M%S%f'"},
                             json)
