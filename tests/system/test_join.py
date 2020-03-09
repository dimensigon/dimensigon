import datetime
import re
from functools import partial
from unittest import TestCase
from unittest.mock import patch

import responses
import rsa
from aioresponses import aioresponses, CallbackResult
from flask_jwt_extended import create_access_token

from dimensigon import join
from dm.domain.entities import Server, Dimension, Catalog
from dm.domain.entities.bootstrap import set_initial
from dm.web import create_app, db


class TestApi(TestCase):

    @patch('dm.domain.entities.get_now')
    def setUp(self, mock_now):
        """Create and configure a new app instance for each test."""
        mock_now.return_value = datetime.datetime(2019, 4, 1)
        # create the app with common test config
        self.app_join = create_app('test')
        self.app_join.config['SECURIZER'] = True
        self.app_join.config['SERVER_NAME'] = 'new'
        with self.app_join.app_context():
            set_initial()
            db.session.commit()
            self.server_new = Server.get_current().to_json()
        self.app = create_app('test')
        self.app.config['SERVER_NAME'] = 'node1'
        self.app.config['SECURIZER'] = True
        self.d_public, self.d_private = rsa.newkeys(2048)
        self.l_public, self.l_private = rsa.newkeys(1024)
        mock_now.return_value = datetime.datetime(2019, 3, 1)
        with self.app.app_context():
            set_initial()
            d = Dimension(name='test', current=True, public=self.d_public, private=self.d_private)
            db.session.add(d)
            db.session.commit()
            self.dimension = d.to_json()
            self.server_node1 = Server.get_current().to_json()

        self.client = self.app.test_client()

    def tearDown(self) -> None:
        with self.app_join.app_context():
            db.session.remove()
            db.drop_all()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('dm.domain.entities.get_now')
    @patch('dimensigon.rsa.newkeys')
    @aioresponses()
    def test_join_command(self, mock_rsa, mock_now, m):
        mock_now.return_value = datetime.datetime(2019, 5, 1)

        mock_rsa.return_value = (self.l_public, self.l_private)

        def request_callback(request, client):
            method_func = getattr(client, request.method.lower())
            resp = method_func(request.path_url, data=request.body, headers=dict(request.headers))

            return resp.status_code, resp.headers, resp.data

        def callback_client(url, **kwargs):
            kwargs.pop('allow_redirects')
            # workarround for https://github.com/pnuckowski/aioresponses/issues/111
            headers = {'Authorization': f"Bearer {create_access_token('test')}"}

            r = self.client.post(url.path, json=kwargs['json'], headers=headers)

            return CallbackResult(r.data, status=r.status_code)

        with self.app.app_context():
            m.post(Server.get_current().url('api_1_0.locker'), callback=callback_client, repeat=True)

        with responses.RequestsMock() as rsps:
            rsps.add_callback(responses.POST,
                              re.compile('^https?://node1.*'),
                              callback=partial(request_callback, client=self.client))
            rsps.add_callback(responses.GET,
                              re.compile('^https?://node1.*'),
                              callback=partial(request_callback, client=self.client))

            with self.app.app_context():
                token = create_access_token('join')

            runner = self.app_join.test_cli_runner()

            result = runner.invoke(join, ['--no-ssl', 'node1:5000', token], catch_exceptions=False)

        with self.app.app_context():
            # check if new server created
            server_new = Server.query.get(self.server_new.get('id'))
            self.assertEqual(server_new.last_modified_at, datetime.datetime(2019, 5, 1))
            server_new.last_modified_at = datetime.datetime(2019, 4, 1)
            self.assertDictEqual(self.server_new, server_new.to_json())

        with self.app_join.app_context():
            self.assertDictEqual(self.dimension, Dimension.get_current().to_json())
            s = Server.query.get(self.server_node1.get('id'))
            self.assertEqual(0, s.route.cost)
            self.assertEqual(1, len(Catalog.query.all()))
            self.assertEqual(datetime.datetime(2019, 5, 1),
                             Catalog.query.filter_by(entity='Server').one().last_modified_at)
