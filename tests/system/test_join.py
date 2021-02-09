import datetime as dt
import functools
import os
import traceback
from unittest import mock
from unittest.mock import patch

import responses
from aioresponses import aioresponses
from flask_jwt_extended import create_access_token
from pyfakefs.fake_filesystem_unittest import TestCase

from dimensigon.__main__ import join
from dimensigon.domain.entities import Server, Dimension
from dimensigon.domain.entities.bootstrap import set_initial
from dimensigon.domain.entities.user import JOIN
from dimensigon.use_cases.catalog import update_db_catalog
from dimensigon.web import db, create_app
from tests.base import OneNodeMixin, virtual_network
from tests.helpers import set_callbacks

now = dt.datetime(2019, 5, 1, tzinfo=dt.timezone.utc)


class TestJoin(OneNodeMixin, TestCase):

    def setUp(self):
        self.maxDiff = None
        self.app_join = create_app('test')
        self.app_join.config['SERVER_NAME'] = 'join'
        self.app_join_context = self.app_join.app_context()
        self.client_join = self.app_join.test_client()
        with self.app_join.app_context():
            db.create_all()
            set_initial(server=False)
            self.join_server_id = Server.set_initial()
            db.session.commit()
            self.mock_dm = mock.MagicMock()
            self.mock_dm.flask_app = self.app_join
            self.mock_dm.engine = db.engine
            self.mock_dm.catalog_manager.db_update_catalog = update_db_catalog

        super().setUp()
        self.app.config['SECURIZER'] = True
        self.app_join.config['SECURIZER'] = True
        self.token = create_access_token(JOIN, user_claims={'applicant': 'me'})
        self.setUpPyfakefs()

        open('/origin_key', 'w').write('keyfile')
        open('/origin_cert', 'w').write('certfile')

    @patch('dimensigon.__main__.time.sleep')
    @patch('dimensigon.web.helpers.current_app')
    @patch('dimensigon.web.api_1_0.urls.use_cases.current_app')
    @patch('dimensigon.domain.entities.route.check_host')
    @patch('dimensigon.domain.entities.get_now')
    def test_join_command(self, mock_now, mock_check, mock_current_app, mock_current_app2, mock_time_sleep):
        with virtual_network(self.app, self.app_join):
            mock_now.return_value = now
            mock_check.return_value = True
            mock_current_app.dm.config.http_conf.get.side_effect = ['/origin_key', '/origin_cert']
            self.mock_dm.config.http_conf.__getitem__.side_effect = {'keyfile': '/dest_key',
                                                                     'certfile': '/dest_cert'}.__getitem__
            mock_current_app2.dm.cluster_manager.get_alive.return_value = [self.s1.id]

            join(self.mock_dm, 'node1', self.token, port=5000)

            # check if new server created
            server_new = Server.query.get(self.join_server_id)
            self.assertEqual(server_new.last_modified_at, now)

            with self.app_join.app_context():
                self.dim.pop('current')
                self.assertDictEqual(self.dim, Dimension.get_current().to_json())
                s = Server.query.get(self.s1.id)
                self.assertEqual(0, s.route.cost)

            self.assertTrue(os.path.exists('/dest_key'))
            self.assertTrue(os.path.exists('/dest_cert'))

    @patch('dimensigon.__main__.requests.get')
    @patch('dimensigon.__main__.time.sleep')
    def test_join_command_error_getting_public_key(self, mock_sleep, mock_get):
        mock_get.return_value = mock.MagicMock()
        mock_get.return_value.status_code.return_code = 400
        mock_get.return_value.__str__ = ''

        with self.assertRaises(SystemExit):
            join(self.mock_dm, 'node1', self.token, port=5000)

    @patch('dimensigon.__main__.time.sleep')
    @responses.activate
    def test_join_command_error_getting_dimension(self, mock_sleep):

        def requests_callback_client(client, request):
            method_func = getattr(client, request.method.lower())
            try:
                resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))
            except Exception as e:
                return 500, {}, traceback.format_exc()

            return resp.status_code, resp.headers, resp.data

        responses.add_callback('GET', 'https://node1:5000/api/v1.0/join/public',
                               callback=functools.partial(requests_callback_client, self.client))

        responses.add('POST', 'https://node1:5000/api/v1.0/join', status=400)
        with self.assertRaises(SystemExit):
            join(self.mock_dm, 'node1', self.token, port=5000)


    @patch('dimensigon.web.api_1_0.urls.use_cases.current_app')
    @patch('dimensigon.domain.entities.route.check_host')
    @patch('dimensigon.domain.entities.get_now')
    @patch('dimensigon.__main__.time.sleep')
    @aioresponses()
    @responses.activate
    def test_join_command_error_updating_catalog(self, mock_time_sleep, mock_now, mock_check, mock_current_app, m):
        # set d
        set_callbacks([("node1", self.client), (r"(127\.0\.0\.1|node2)", self.client_join)], m)
        mock_now.return_value = now
        mock_check.return_value = True
        mock_current_app.dm.config.http_conf.get.side_effect = ['/origin_key', '/origin_cert']
        self.mock_dm.config.http_conf.__getitem__.side_effect = {'keyfile': '/dest_key',
                                                                 'certfile': '/dest_cert'}.__getitem__
        with self.app_join.app_context():
            self.mock_dm.catalog_manager = mock.Mock()
            self.mock_dm.catalog_manager.db_update_catalog.side_effect = RuntimeError()

        with self.assertRaises(SystemExit):
            join(self.mock_dm, 'node1', self.token, port=5000)

